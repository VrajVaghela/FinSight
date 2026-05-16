"use client";

import { useState, useEffect, useCallback } from "react";
import type { ProjectRecord } from "@/types";
import { fetchProjects, createProject, deleteProject } from "@/lib/api";

export function useProjects() {
// ... existing state and loadProjects ...
  const [projects, setProjects] = useState<ProjectRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadProjects = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchProjects();
      setProjects(data);
      setError(null);
    } catch {
      // If backend is not reachable, use mock data for development
      setProjects([]);
      setError("Could not connect to backend");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProjects();
  }, [loadProjects]);

  const addProject = useCallback(
    async (name: string, systemPrompt?: string) => {
      try {
        const project = await createProject(name, systemPrompt);
        setProjects((prev) => [...prev, project]);
        return project;
      } catch {
        setError("Failed to create project");
        return null;
      }
    },
    []
  );

  const removeProject = useCallback(
    async (id: string) => {
      try {
        await deleteProject(id);
        setProjects((prev) => prev.filter(p => p.id !== id));
        return true;
      } catch {
        setError("Failed to delete project");
        return false;
      }
    },
    []
  );

  return { projects, loading, error, addProject, removeProject, refresh: loadProjects };
}
