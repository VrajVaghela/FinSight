"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Layers,
  FolderOpen,
  Folder,
  FileText,
  BarChart3,
  Settings,
  UploadCloud,
  Plus,
  ChevronRight,
  ChevronDown,
  MessageSquare,
  File,
  Hash,
  PanelLeftClose,
  PanelLeftOpen,
  Trash2,
  LogOut,
} from "lucide-react";
import { useProjects } from "@/hooks/useProjects";
import { useAuth } from "@/hooks/useAuth";
import NewProjectModal from "./NewProjectModal";
import { fetchConversations } from "@/lib/api";

interface StandaloneChat {
  id: string;
  title: string;
  lastMessage: string;
  project_id: string;
}

export default function Sidebar() {
  const pathname = usePathname();
  const router = useRouter();
  const { logout } = useAuth();
  const { projects, addProject, removeProject } = useProjects();
  const [showModal, setShowModal] = useState(false);
  const [expandedProject, setExpandedProject] = useState<string | null>(null);
  const [isCollapsed, setIsCollapsed] = useState(false);

  // Standalone chats fetched from API
  const [standaloneChats, setStandaloneChats] = useState<StandaloneChat[]>([]);

  // Refresh conversations on mount and whenever the pathname changes (e.g., after navigating to a new chat)
  useEffect(() => {
    const loadConversations = () => {
      fetchConversations().then((conversations: any[]) => {
        setStandaloneChats(conversations.map(c => ({
          id: c.id,
          title: c.title,
          lastMessage: "Click to view history",
          project_id: c.project_id
        })));
      }).catch(console.error);
    };

    loadConversations();

    // Also refresh every 10 seconds so new conversations appear
    const interval = setInterval(loadConversations, 10000);
    return () => clearInterval(interval);
  }, [pathname]);

  const currentProjectId = pathname.match(/\/projects\/([^/]+)/)?.[1] || null;
  const currentChatId = pathname.match(/\/chats\/([^/]+)/)?.[1] || null;

  const navItems = [
    { href: "/analytics", icon: BarChart3, label: "Analytics" },
    { href: "/settings", icon: Settings, label: "Settings" },
  ];

  return (
    <>
      <aside
        className="animate-slide-left"
        style={{
          width: isCollapsed ? 72 : 272,
          display: "flex",
          flexDirection: "column",
          background: "#111111",
          borderRight: "1px solid #2a2a2a",
          height: "100vh",
          transition: "width 0.3s cubic-bezier(0.16, 1, 0.3, 1)",
          overflow: "hidden",
          flexShrink: 0,
        }}
      >
        {/* Logo & Toggle */}
        <div style={{ padding: "24px 20px 20px", display: "flex", alignItems: "center", justifyContent: isCollapsed ? "center" : "space-between" }}>
          {!isCollapsed && (
            <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div
                style={{
                  width: 36,
                  height: 36,
                  background: "linear-gradient(135deg, #22c55e, #16a34a)",
                  borderRadius: 10,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Layers style={{ width: 18, height: 18, color: "black" }} />
              </div>
              <div style={{ display: "flex", alignItems: "center", whiteSpace: "nowrap" }}>
                <span style={{ fontSize: 16, fontWeight: 800, color: "#fafafa", letterSpacing: "-0.02em" }}>
                  FinSight
                </span>
                <span style={{ fontSize: 16, fontWeight: 600, color: "#22c55e" }}>AI</span>
              </div>
            </div>
          )}
          
          <button
            onClick={() => setIsCollapsed(!isCollapsed)}
            style={{
              background: "transparent",
              border: "none",
              color: "#666",
              cursor: "pointer",
              padding: isCollapsed ? 8 : 4,
              borderRadius: 6,
            }}
            title={isCollapsed ? "Expand Sidebar" : "Collapse Sidebar"}
          >
            {isCollapsed ? <PanelLeftOpen size={20} /> : <PanelLeftClose size={18} />}
          </button>
        </div>

        {/* New Chat + New Project buttons */}
        <div style={{ padding: "0 12px 8px", display: "flex", gap: 6, justifyContent: isCollapsed ? "center" : "flex-start", flexDirection: isCollapsed ? "column" : "row" }}>
          {isCollapsed ? (
             <Link
             href="/chats/new"
             style={{
               display: "flex",
               alignItems: "center",
               justifyContent: "center",
               width: 36,
               height: 36,
               background: "#191919",
               border: "1px solid #2a2a2a",
               borderRadius: 10,
               color: "#888",
               textDecoration: "none",
             }}
             title="New Chat"
           >
             <Plus style={{ width: 14, height: 14 }} />
           </Link>
          ) : (
            <Link
              href="/chats/new"
              style={{
                flex: 1,
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "9px 12px",
                background: "#191919",
                border: "1px solid #2a2a2a",
                borderRadius: 10,
                color: "#888",
                fontSize: 12,
                fontWeight: 600,
                textDecoration: "none",
              }}
            >
              <Plus style={{ width: 13, height: 13 }} />
              New Chat
            </Link>
          )}

          <button
            onClick={() => setShowModal(true)}
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: 36,
              height: 36,
              background: "#191919",
              border: "1px solid #2a2a2a",
              borderRadius: 10,
              color: "#888",
              cursor: "pointer",
            }}
            title="New Project"
          >
            <FolderOpen style={{ width: 14, height: 14 }} />
          </button>
        </div>

        <div style={{ flex: 1, overflow: "auto", overflowX: "hidden", padding: "0 12px" }}>

          {/* ── Projects ──────────────────────────── */}
          <div style={{ marginBottom: 20 }}>
            {!isCollapsed && (
              <p style={{
                fontSize: 10,
                fontWeight: 700,
                color: "#444",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                padding: "8px 8px 6px",
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                Projects
              </p>
            )}
            <div style={{ display: "flex", flexDirection: "column", gap: 1, alignItems: isCollapsed ? "center" : "stretch" }}>
              {projects.length === 0 ? (
                !isCollapsed && (
                  <button
                    onClick={() => setShowModal(true)}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 8,
                      padding: "8px 10px",
                      borderRadius: 8,
                      fontSize: 12,
                      color: "#444",
                      background: "transparent",
                      border: "1px dashed #2a2a2a",
                      cursor: "pointer",
                      fontStyle: "italic",
                    }}
                  >
                    <Plus style={{ width: 12, height: 12 }} />
                    Create a project
                  </button>
                )
              ) : (
                projects.map((project) => {
                  const isActive = currentProjectId === project.id;
                  const isExpanded = expandedProject === project.id;
                  
                  return (
                    <div key={project.id} className="animate-fade-up" style={{ width: isCollapsed ? 40 : "100%" }}>
                      {/* Project Header */}
                      <div
                        className="group"
                        style={{
                          width: "100%",
                          height: isCollapsed ? 40 : "auto",
                          display: "flex",
                          alignItems: "center",
                          justifyContent: isCollapsed ? "center" : "flex-start",
                          gap: 8,
                          padding: "8px 10px",
                          borderRadius: 8,
                          background: isActive ? "rgba(34,197,94,0.06)" : "transparent",
                          cursor: "pointer",
                        }}
                        onClick={() => {
                          if (isCollapsed) setIsCollapsed(false);
                          setExpandedProject(isExpanded && !isCollapsed ? null : project.id);
                        }}
                        title={project.name}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: 8, flex: 1, overflow: "hidden" }}>
                          {!isCollapsed && (
                            isExpanded ? (
                              <ChevronDown style={{ width: 12, height: 12, color: "#555", flexShrink: 0 }} />
                            ) : (
                              <ChevronRight style={{ width: 12, height: 12, color: "#555", flexShrink: 0 }} />
                            )
                          )}
                          {isActive ? (
                            <FolderOpen style={{ width: 14, height: 14, color: "#22c55e", flexShrink: 0 }} />
                          ) : (
                            <Folder style={{ width: 14, height: 14, color: "#555", flexShrink: 0 }} />
                          )}
                          {!isCollapsed && (
                            <span style={{ fontSize: 13, fontWeight: isActive ? 700 : 500, color: isActive ? "#fafafa" : "#777", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                              {project.name}
                            </span>
                          )}
                        </div>
                        {!isCollapsed && (
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            <span style={{
                              fontSize: 9,
                              color: "#444",
                              fontFamily: "'JetBrains Mono', monospace",
                            }}>
                              {project.file_count ?? project.file_ids?.length ?? 0}
                            </span>
                            <button
                              onClick={(e) => {
                                e.stopPropagation();
                                if (confirm(`Are you sure you want to delete ${project.name}?`)) {
                                  removeProject(project.id);
                                }
                              }}
                              className="opacity-0 group-hover:opacity-100 transition-opacity"
                              style={{
                                background: "transparent",
                                border: "none",
                                cursor: "pointer",
                                padding: 2,
                                display: "flex",
                                alignItems: "center",
                                color: "#ef4444",
                              }}
                              title="Delete Project"
                            >
                              <Trash2 size={12} />
                            </button>
                          </div>
                        )}
                      </div>

                      {/* Expanded: Files + Chats */}
                      {isExpanded && !isCollapsed && (
                        <div className="animate-fade-in" style={{ marginLeft: 18, borderLeft: "1px solid #222", paddingLeft: 12, marginTop: 2, marginBottom: 4 }}>
                          {/* Context */}
                          <Link
                            href={`/projects/${project.id}`}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: 8,
                              padding: "6px 8px",
                              borderRadius: 6,
                              fontSize: 12,
                              color: "#666",
                              textDecoration: "none",
                            }}
                          >
                            <FileText style={{ width: 12, height: 12 }} />
                            Context & Files
                          </Link>

                          {/* Project documents */}
                          {project.documents && project.documents.length > 0 && (
                            <div style={{ marginTop: 8 }}>
                              <p style={{
                                fontSize: 9,
                                fontWeight: 700,
                                color: "#444",
                                textTransform: "uppercase",
                                letterSpacing: "0.08em",
                                padding: "4px 8px",
                                fontFamily: "'JetBrains Mono', monospace",
                              }}>
                                Documents
                              </p>
                              {project.documents.map((doc) => (
                                <div
                                  key={doc.id}
                                  title={doc.name}
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 6,
                                    padding: "4px 8px",
                                    borderRadius: 6,
                                    fontSize: 11,
                                    color: "#888",
                                  }}
                                >
                                  <FileText style={{ width: 10, height: 10, flexShrink: 0 }} />
                                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                    {doc.name}
                                  </span>
                                </div>
                              ))}
                            </div>
                          )}

                          {/* Separator */}
                          <div style={{ height: 1, background: "#1e1e1e", margin: "6px 0" }} />

                          {/* Project chats */}
                          {(() => {
                            const projectChats = standaloneChats.filter(c => c.project_id === project.id);
                            if (projectChats.length === 0) return null;
                            return (
                            <div style={{ marginTop: 8 }}>
                              <p style={{
                                fontSize: 9,
                                fontWeight: 700,
                                color: "#444",
                                textTransform: "uppercase",
                                letterSpacing: "0.08em",
                                padding: "4px 8px",
                                fontFamily: "'JetBrains Mono', monospace",
                              }}>
                                Chats
                              </p>
                              {projectChats.map((conv) => (
                                <Link
                                  key={conv.id}
                                  href={`/projects/${project.id}/chat/${conv.id}`}
                                  style={{
                                    display: "flex",
                                    alignItems: "center",
                                    gap: 6,
                                    padding: "5px 8px",
                                    borderRadius: 6,
                                    fontSize: 11,
                                    color: currentChatId === conv.id ? "#fafafa" : "#666",
                                    background: currentChatId === conv.id ? "#1a1a1a" : "transparent",
                                    textDecoration: "none",
                                    fontWeight: currentChatId === conv.id ? 600 : 400,
                                  }}
                                >
                                  <MessageSquare style={{ width: 10, height: 10, flexShrink: 0, color: currentChatId === conv.id ? "#fafafa" : "#666" }} />
                                  <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                                    {conv.title}
                                  </span>
                                </Link>
                              ))}
                            </div>
                            );
                          })()}

                          {/* New chat under project */}
                          <Link
                            href={`/projects/${project.id}/chat`}
                            style={{
                              display: "flex",
                              alignItems: "center",
                              gap: 6,
                              padding: "5px 8px",
                              borderRadius: 6,
                              fontSize: 11,
                              color: "#22c55e",
                              textDecoration: "none",
                              fontWeight: 600,
                              marginTop: 4,
                            }}
                          >
                            <Plus style={{ width: 10, height: 10 }} />
                            New Chat
                          </Link>
                        </div>
                      )}
                    </div>
                  );
                })
              )}
            </div>
          </div>

          {/* ── Navigate ──────────────────────────── */}
          <div>
            {!isCollapsed && (
              <p style={{
                fontSize: 10,
                fontWeight: 700,
                color: "#444",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                padding: "8px 8px 6px",
                fontFamily: "'JetBrains Mono', monospace",
              }}>
                Navigate
              </p>
            )}
            <div style={{ display: "flex", flexDirection: "column", gap: 1, alignItems: isCollapsed ? "center" : "stretch" }}>
              {navItems.map((item) => {
                const isActive = pathname.startsWith(item.href);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    title={item.label}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: isCollapsed ? "center" : "flex-start",
                      gap: 10,
                      padding: "8px 10px",
                      borderRadius: 8,
                      fontSize: 13,
                      fontWeight: isActive ? 600 : 500,
                      color: isActive ? "#fafafa" : "#777",
                      background: isActive ? "#1a1a1a" : "transparent",
                      textDecoration: "none",
                      width: isCollapsed ? 40 : "auto",
                      height: isCollapsed ? 40 : "auto",
                    }}
                  >
                    <item.icon style={{ width: 15, height: 15, color: isActive ? "#fafafa" : "#555" }} />
                    {!isCollapsed && item.label}
                  </Link>
                );
              })}
              
              <button
                onClick={logout}
                title="Logout"
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: isCollapsed ? "center" : "flex-start",
                  gap: 10,
                  padding: "8px 10px",
                  borderRadius: 8,
                  fontSize: 13,
                  fontWeight: 500,
                  color: "#ef4444",
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                  width: isCollapsed ? 40 : "auto",
                  height: isCollapsed ? 40 : "auto",
                  marginTop: 8,
                }}
              >
                <LogOut style={{ width: 15, height: 15, color: "#ef4444" }} />
                {!isCollapsed && "Logout"}
              </button>
            </div>
          </div>
        </div>

        {/* Bottom — Upload */}
        <div style={{ padding: "12px", borderTop: "1px solid #1e1e1e", display: "flex", flexDirection: "column", alignItems: isCollapsed ? "center" : "stretch" }}>
          {!isCollapsed && (
            <div
              style={{
                padding: "12px 14px",
                background: "#151515",
                border: "1px solid #2a2a2a",
                borderRadius: 10,
                marginBottom: 10,
              }}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
                <span style={{ fontSize: 10, fontWeight: 700, color: "#555", fontFamily: "'JetBrains Mono', monospace" }}>Usage</span>
                <span style={{ fontSize: 10, fontWeight: 700, color: "#22c55e", fontFamily: "'JetBrains Mono', monospace" }}>75%</span>
              </div>
              <div style={{ width: "100%", height: 3, background: "#222", borderRadius: 99, overflow: "hidden" }}>
                <div style={{ width: "75%", height: "100%", background: "linear-gradient(90deg, #22c55e, #a78bfa)", borderRadius: 99 }} />
              </div>
              <p style={{ fontSize: 9, color: "#444", marginTop: 4, fontFamily: "'JetBrains Mono', monospace" }}>750 / 1,000 pages</p>
            </div>
          )}

          <button
            onClick={() => {
              const targetProjectId = currentProjectId || projects[0]?.id;
              if (targetProjectId) {
                router.push(`/projects/${targetProjectId}`);
              } else {
                setShowModal(true);
              }
            }}
            style={{
              width: isCollapsed ? 40 : "100%",
              height: isCollapsed ? 40 : "auto",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 8,
              padding: isCollapsed ? 0 : "10px 0",
              background: "#22c55e",
              color: "black",
              borderRadius: 10,
              fontSize: 13,
              fontWeight: 700,
              border: "none",
              cursor: "pointer",
            }}
            title="Upload Document"
          >
            <UploadCloud style={{ width: 15, height: 15 }} />
            {!isCollapsed && "Upload Document"}
          </button>
        </div>
      </aside>

      {showModal && (
        <NewProjectModal
          onClose={() => setShowModal(false)}
          onCreate={async (name, prompt) => {
            const project = await addProject(name, prompt);
            if (!project) return false;
            setShowModal(false);
            router.push(`/projects/${project.id}`);
            return true;
          }}
        />
      )}
    </>
  );
}
