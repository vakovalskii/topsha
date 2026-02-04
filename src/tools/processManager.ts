/**
 * Process Manager - tracks and cleans up user processes
 * 
 * Features:
 * - Track background processes per user
 * - Kill processes when user inactive for TTL
 * - Periodic cleanup
 */

import { spawn, ChildProcess, execSync } from 'child_process';
import { CONFIG } from '../config.js';

interface UserProcess {
  pid: number;
  command: string;
  startTime: number;
  userId: string;
}

interface UserActivity {
  lastActive: number;
  processes: UserProcess[];
}

// Track user activity and processes
const userActivity = new Map<string, UserActivity>();

/**
 * Mark user as active (called on each request)
 */
export function markUserActive(userId: string): void {
  const activity = userActivity.get(userId) || { 
    lastActive: Date.now(), 
    processes: [] 
  };
  activity.lastActive = Date.now();
  userActivity.set(userId, activity);
}

/**
 * Register a background process for a user
 */
export function registerProcess(userId: string, pid: number, command: string): void {
  const activity = userActivity.get(userId) || { 
    lastActive: Date.now(), 
    processes: [] 
  };
  
  activity.processes.push({
    pid,
    command: command.slice(0, 100),
    startTime: Date.now(),
    userId,
  });
  
  activity.lastActive = Date.now();
  userActivity.set(userId, activity);
  
  console.log(`[procmgr] Registered PID ${pid} for user ${userId}: ${command.slice(0, 50)}`);
}

/**
 * Kill a specific process
 */
function killProcess(proc: UserProcess): boolean {
  try {
    process.kill(proc.pid, 'SIGTERM');
    console.log(`[procmgr] Killed PID ${proc.pid} (user ${proc.userId})`);
    return true;
  } catch (e) {
    // Process already dead
    return false;
  }
}

/**
 * Kill all processes for a user
 */
export function killUserProcesses(userId: string): number {
  const activity = userActivity.get(userId);
  if (!activity) return 0;
  
  let killed = 0;
  for (const proc of activity.processes) {
    if (killProcess(proc)) killed++;
  }
  
  activity.processes = [];
  console.log(`[procmgr] Killed ${killed} processes for user ${userId}`);
  return killed;
}

/**
 * Clean up processes for inactive users
 */
export function cleanupInactiveUsers(): void {
  const now = Date.now();
  const ttlMs = CONFIG.sandbox.userInactivityTTL * 60 * 1000;
  
  for (const [userId, activity] of userActivity.entries()) {
    const inactive = now - activity.lastActive;
    
    if (inactive > ttlMs && activity.processes.length > 0) {
      console.log(`[procmgr] User ${userId} inactive for ${Math.round(inactive / 60000)}min, cleaning up...`);
      
      // Kill all user processes
      const killed = killUserProcesses(userId);
      
      if (killed > 0) {
        console.log(`[procmgr] Cleaned up ${killed} processes for inactive user ${userId}`);
      }
    }
    
    // Also clean up stale process entries (processes that died on their own)
    activity.processes = activity.processes.filter(proc => {
      try {
        process.kill(proc.pid, 0); // Check if alive
        return true;
      } catch {
        return false; // Dead, remove from list
      }
    });
  }
}

/**
 * Clean up old processes that exceeded background timeout
 */
export function cleanupOldProcesses(): void {
  const now = Date.now();
  const maxAge = CONFIG.sandbox.backgroundTimeout * 1000;
  
  for (const [userId, activity] of userActivity.entries()) {
    for (const proc of activity.processes) {
      const age = now - proc.startTime;
      
      if (age > maxAge) {
        console.log(`[procmgr] Process ${proc.pid} exceeded max age (${Math.round(age / 1000)}s), killing...`);
        killProcess(proc);
      }
    }
  }
}

/**
 * Get stats for diagnostics
 */
export function getProcessStats(): object {
  const stats = {
    totalUsers: userActivity.size,
    totalProcesses: 0,
    users: [] as any[],
  };
  
  for (const [userId, activity] of userActivity.entries()) {
    stats.totalProcesses += activity.processes.length;
    
    if (activity.processes.length > 0) {
      stats.users.push({
        userId,
        lastActive: new Date(activity.lastActive).toISOString(),
        inactiveMin: Math.round((Date.now() - activity.lastActive) / 60000),
        processes: activity.processes.length,
      });
    }
  }
  
  return stats;
}

/**
 * Start the cleanup scheduler
 */
export function startProcessManager(): void {
  const intervalMs = CONFIG.sandbox.cleanupInterval * 60 * 1000;
  
  console.log(`[procmgr] Started (cleanup every ${CONFIG.sandbox.cleanupInterval}min, TTL ${CONFIG.sandbox.userInactivityTTL}min)`);
  
  setInterval(() => {
    cleanupInactiveUsers();
    cleanupOldProcesses();
  }, intervalMs);
}

/**
 * Kill all tracked processes (for shutdown)
 */
export function killAllProcesses(): void {
  let total = 0;
  
  for (const [userId] of userActivity.entries()) {
    total += killUserProcesses(userId);
  }
  
  console.log(`[procmgr] Shutdown: killed ${total} processes`);
}
