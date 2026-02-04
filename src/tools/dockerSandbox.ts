/**
 * Docker Sandbox - isolated container per user
 * 
 * Features:
 * - One container per active user
 * - Workspace mounted (only user's own)
 * - Ports forwarded (user's range)
 * - No access to secrets or other users
 * - Auto-cleanup after inactivity
 */

import Docker from 'dockerode';
import { CONFIG } from '../config.js';

const docker = new Docker({ socketPath: '/var/run/docker.sock' });

const SANDBOX_IMAGE = 'python:3.11-alpine';
const CONTAINER_PREFIX = 'sandbox_';

interface UserContainer {
  containerId: string;
  userId: string;
  ports: number[];
  lastActive: number;
  created: number;
}

// Track active user containers
const userContainers = new Map<string, UserContainer>();

/**
 * Calculate port range for user
 * Sandbox uses 5000-5099 range (separate from gateway's 4000-4099)
 */
function getUserPorts(userId: string): { base: number; range: number[] } {
  const userIndex = parseInt(userId) % 10;
  const basePort = 5000 + (userIndex * 10);  // 5000-5099 for sandbox
  const range = Array.from({ length: 10 }, (_, i) => basePort + i);
  return { base: basePort, range };
}

/**
 * Build port bindings for Docker
 */
function buildPortBindings(ports: number[]): Docker.PortMap {
  const bindings: Docker.PortMap = {};
  for (const port of ports) {
    bindings[`${port}/tcp`] = [{ HostPort: String(port) }];
  }
  return bindings;
}

/**
 * Build exposed ports config
 */
function buildExposedPorts(ports: number[]): { [port: string]: {} } {
  const exposed: { [port: string]: {} } = {};
  for (const port of ports) {
    exposed[`${port}/tcp`] = {};
  }
  return exposed;
}

/**
 * Get or create container for user
 */
export async function getOrCreateContainer(userId: string): Promise<UserContainer> {
  // Check if already have container
  const existing = userContainers.get(userId);
  if (existing) {
    // Verify it's still running
    try {
      const container = docker.getContainer(existing.containerId);
      const info = await container.inspect();
      if (info.State.Running) {
        existing.lastActive = Date.now();
        return existing;
      }
    } catch {
      // Container gone, remove from map
      userContainers.delete(userId);
    }
  }
  
  // Create new container
  const { range: ports } = getUserPorts(userId);
  const containerName = `${CONTAINER_PREFIX}${userId}`;
  
  // Remove old container if exists
  try {
    const old = docker.getContainer(containerName);
    await old.stop().catch(() => {});
    await old.remove().catch(() => {});
  } catch {
    // Container doesn't exist, ok
  }
  
  console.log(`[sandbox] Creating container for user ${userId}, ports ${ports[0]}-${ports[9]}`);
  
  const container = await docker.createContainer({
    name: containerName,
    Image: SANDBOX_IMAGE,
    Cmd: ['sleep', 'infinity'],  // Keep alive
    WorkingDir: `/workspace/${userId}`,
    Env: [
      `USER_ID=${userId}`,
      `PORT_BASE=${ports[0]}`,
      `PORTS=${ports.join(',')}`,
    ],
    ExposedPorts: buildExposedPorts(ports),
    HostConfig: {
      Binds: [
        // Only mount user's workspace!
        `/home/ubuntu/LocalTopSH/workspace/${userId}:/workspace/${userId}:rw`,
      ],
      PortBindings: buildPortBindings(ports),
      Memory: 512 * 1024 * 1024,  // 512MB
      MemorySwap: 512 * 1024 * 1024,  // No swap
      CpuPeriod: 100000,
      CpuQuota: 50000,  // 50% CPU
      PidsLimit: 100,   // Max processes
      NetworkMode: 'bridge',
      AutoRemove: false,  // We manage lifecycle
      SecurityOpt: ['no-new-privileges'],
    },
  });
  
  await container.start();
  
  // Install common tools
  await execRaw(container.id, 'apk add --no-cache curl git jq nodejs npm bash');
  
  const userContainer: UserContainer = {
    containerId: container.id,
    userId,
    ports,
    lastActive: Date.now(),
    created: Date.now(),
  };
  
  userContainers.set(userId, userContainer);
  console.log(`[sandbox] Container ${container.id.slice(0, 12)} ready for user ${userId}`);
  
  return userContainer;
}

/**
 * Execute command in container (raw, no wrapper)
 */
async function execRaw(containerId: string, cmd: string): Promise<{ stdout: string; stderr: string; exitCode: number }> {
  const container = docker.getContainer(containerId);
  
  const exec = await container.exec({
    Cmd: ['sh', '-c', cmd],
    AttachStdout: true,
    AttachStderr: true,
    WorkingDir: `/workspace`,
  });
  
  const stream = await exec.start({ hijack: true, stdin: false });
  
  return new Promise((resolve) => {
    let stdout = '';
    let stderr = '';
    
    stream.on('data', (chunk: Buffer) => {
      // Docker multiplexes stdout/stderr in stream
      // First 8 bytes are header: [type, 0, 0, 0, size1, size2, size3, size4]
      let offset = 0;
      while (offset < chunk.length) {
        if (offset + 8 > chunk.length) break;
        
        const type = chunk[offset];
        const size = chunk.readUInt32BE(offset + 4);
        
        if (offset + 8 + size > chunk.length) break;
        
        const payload = chunk.slice(offset + 8, offset + 8 + size).toString();
        
        if (type === 1) {
          stdout += payload;
        } else if (type === 2) {
          stderr += payload;
        }
        
        offset += 8 + size;
      }
    });
    
    stream.on('end', async () => {
      const info = await exec.inspect();
      resolve({
        stdout: stdout.trim(),
        stderr: stderr.trim(),
        exitCode: info.ExitCode || 0,
      });
    });
    
    stream.on('error', () => {
      resolve({ stdout, stderr, exitCode: 1 });
    });
  });
}

/**
 * Execute command in user's sandbox
 */
export async function executeInSandbox(
  userId: string, 
  command: string,
  cwd?: string
): Promise<{ success: boolean; output: string; sandboxed: boolean }> {
  try {
    const { containerId } = await getOrCreateContainer(userId);
    const container = docker.getContainer(containerId);
    
    // Build exec with proper working directory
    const workDir = cwd || `/workspace/${userId}`;
    
    const exec = await container.exec({
      Cmd: ['sh', '-c', command],
      AttachStdout: true,
      AttachStderr: true,
      WorkingDir: workDir,
    });
    
    const stream = await exec.start({ hijack: true, stdin: false });
    
    return new Promise((resolve) => {
      let stdout = '';
      let stderr = '';
      
      // Timeout
      const timeout = setTimeout(() => {
        stream.destroy();
        resolve({
          success: false,
          output: `Timeout: command exceeded ${CONFIG.sandbox.commandTimeout}s`,
          sandboxed: true,
        });
      }, CONFIG.sandbox.commandTimeout * 1000);
      
      stream.on('data', (chunk: Buffer) => {
        let offset = 0;
        while (offset < chunk.length) {
          if (offset + 8 > chunk.length) break;
          
          const type = chunk[offset];
          const size = chunk.readUInt32BE(offset + 4);
          
          if (offset + 8 + size > chunk.length) break;
          
          const payload = chunk.slice(offset + 8, offset + 8 + size).toString();
          
          if (type === 1) {
            stdout += payload;
          } else if (type === 2) {
            stderr += payload;
          }
          
          offset += 8 + size;
        }
      });
      
      stream.on('end', async () => {
        clearTimeout(timeout);
        const info = await exec.inspect();
        const output = stdout || stderr || '(no output)';
        
        resolve({
          success: info.ExitCode === 0,
          output: output.trim().slice(0, 50000),  // Limit output
          sandboxed: true,
        });
      });
      
      stream.on('error', (err) => {
        clearTimeout(timeout);
        resolve({
          success: false,
          output: `Error: ${err.message}`,
          sandboxed: true,
        });
      });
    });
    
  } catch (err: any) {
    console.error(`[sandbox] Error for user ${userId}:`, err.message);
    return {
      success: false,
      output: `Sandbox error: ${err.message}`,
      sandboxed: false,
    };
  }
}

/**
 * Mark user as active
 */
export function markUserActive(userId: string): void {
  const container = userContainers.get(userId);
  if (container) {
    container.lastActive = Date.now();
  }
}

/**
 * Stop and remove user's container
 */
export async function stopUserContainer(userId: string): Promise<void> {
  const container = userContainers.get(userId);
  if (!container) return;
  
  try {
    const c = docker.getContainer(container.containerId);
    await c.stop({ t: 5 });
    await c.remove();
    console.log(`[sandbox] Removed container for user ${userId}`);
  } catch (err: any) {
    console.log(`[sandbox] Failed to remove container for ${userId}: ${err.message}`);
  }
  
  userContainers.delete(userId);
}

/**
 * Cleanup inactive user containers
 */
export async function cleanupInactiveContainers(): Promise<void> {
  const now = Date.now();
  const ttlMs = CONFIG.sandbox.userInactivityTTL * 60 * 1000;
  
  for (const [userId, container] of userContainers.entries()) {
    const inactive = now - container.lastActive;
    
    if (inactive > ttlMs) {
      console.log(`[sandbox] User ${userId} inactive for ${Math.round(inactive / 60000)}min, removing container...`);
      await stopUserContainer(userId);
    }
  }
}

/**
 * Get sandbox stats
 */
export function getSandboxStats(): object {
  return {
    activeContainers: userContainers.size,
    containers: Array.from(userContainers.values()).map(c => ({
      userId: c.userId,
      containerId: c.containerId.slice(0, 12),
      ports: `${c.ports[0]}-${c.ports[9]}`,
      ageMin: Math.round((Date.now() - c.created) / 60000),
      inactiveMin: Math.round((Date.now() - c.lastActive) / 60000),
    })),
  };
}

/**
 * Check if Docker is available
 */
export async function isDockerAvailable(): Promise<boolean> {
  try {
    await docker.ping();
    return true;
  } catch {
    return false;
  }
}

/**
 * Pull sandbox image if needed
 */
export async function ensureSandboxImage(): Promise<void> {
  try {
    await docker.getImage(SANDBOX_IMAGE).inspect();
    console.log(`[sandbox] Image ${SANDBOX_IMAGE} ready`);
  } catch {
    console.log(`[sandbox] Pulling image ${SANDBOX_IMAGE}...`);
    await new Promise((resolve, reject) => {
      docker.pull(SANDBOX_IMAGE, (err: any, stream: any) => {
        if (err) return reject(err);
        docker.modem.followProgress(stream, (err: any) => {
          if (err) reject(err);
          else resolve(undefined);
        });
      });
    });
    console.log(`[sandbox] Image ${SANDBOX_IMAGE} pulled`);
  }
}

/**
 * Start sandbox manager
 */
export async function startSandboxManager(): Promise<void> {
  const available = await isDockerAvailable();
  
  if (!available) {
    console.log('[sandbox] Docker not available! Running without sandbox.');
    return;
  }
  
  await ensureSandboxImage();
  
  // Cleanup interval
  const intervalMs = CONFIG.sandbox.cleanupInterval * 60 * 1000;
  setInterval(() => {
    cleanupInactiveContainers();
  }, intervalMs);
  
  console.log(`[sandbox] Manager started (cleanup every ${CONFIG.sandbox.cleanupInterval}min, TTL ${CONFIG.sandbox.userInactivityTTL}min)`);
}

/**
 * Shutdown - remove all containers
 */
export async function shutdownSandbox(): Promise<void> {
  console.log('[sandbox] Shutting down, removing all containers...');
  
  for (const [userId] of userContainers.entries()) {
    await stopUserContainer(userId);
  }
}
