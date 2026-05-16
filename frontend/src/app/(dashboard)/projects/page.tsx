"use client";

import { useState } from "react";
import { useProjects } from "@/hooks/useProjects";
import Header from "@/components/Header";
import NewProjectModal from "@/components/NewProjectModal";
import Link from "next/link";
import {
  Plus,
  FolderOpen,
  Sparkles,
  FileSearch,
  Shield,
  ArrowRight,
} from "lucide-react";

export default function ProjectsPage() {
  const { projects, addProject } = useProjects();
  const [showModal, setShowModal] = useState(false);

  return (
    <>
      <Header />
      <div style={{ flex: 1, overflow: "auto", padding: "32px 32px" }}>
        <div className="animate-fade-up" style={{ maxWidth: 900, margin: "0 auto" }}>
          {/* Header */}
          <div
            style={{
              display: "flex",
              justifyContent: "space-between",
              alignItems: "center",
              marginBottom: 32,
            }}
          >
            <div>
              <h1
                style={{
                  fontSize: 24,
                  fontWeight: 800,
                  color: "#fafafa",
                  letterSpacing: "-0.03em",
                }}
              >
                Projects
              </h1>
              <p style={{ fontSize: 14, color: "#555", marginTop: 4 }}>
                Manage your document analysis workspaces
              </p>
            </div>
            <button
              onClick={() => setShowModal(true)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                padding: "10px 18px",
                background: "#22c55e",
                color: "black",
                borderRadius: 10,
                fontSize: 13,
                fontWeight: 700,
                border: "none",
                cursor: "pointer",
                transition: "all 0.2s ease",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "#16a34a";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "#22c55e";
              }}
            >
              <Plus style={{ width: 16, height: 16 }} />
              New Project
            </button>
          </div>

          {projects.length === 0 ? (
            /* Empty State */
            <div
              className="animate-fade-up"
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                paddingTop: 80,
                paddingBottom: 80,
              }}
            >
              <div
                className="animate-glow"
                style={{
                  width: 64,
                  height: 64,
                  borderRadius: 20,
                  background: "rgba(34,197,94,0.06)",
                  border: "1px solid rgba(34,197,94,0.12)",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  marginBottom: 24,
                }}
              >
                <Sparkles style={{ width: 28, height: 28, color: "#22c55e" }} />
              </div>

              <h2
                style={{
                  fontSize: 20,
                  fontWeight: 700,
                  color: "#fafafa",
                  marginBottom: 8,
                  letterSpacing: "-0.02em",
                }}
              >
                Welcome to FinSight AI
              </h2>
              <p
                style={{
                  fontSize: 14,
                  color: "#666",
                  textAlign: "center",
                  maxWidth: 400,
                  lineHeight: 1.6,
                  marginBottom: 32,
                }}
              >
                Upload financial documents and get AI-powered insights with
                grounded citations and numeric precision.
              </p>

              <div
                className="stagger-children"
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(3, 1fr)",
                  gap: 16,
                  width: "100%",
                  maxWidth: 640,
                }}
              >
                {[
                  {
                    icon: FileSearch,
                    title: "Document Ingestion",
                    desc: "Docling-powered PDF parsing with table structure preservation",
                    color: "#22c55e",
                  },
                  {
                    icon: Sparkles,
                    title: "Grounded RAG",
                    desc: "Every answer backed by citations traceable to the source",
                    color: "#a78bfa",
                  },
                  {
                    icon: Shield,
                    title: "4-Level Refusal",
                    desc: "If evidence isn't in the document, we refuse — never fabricate",
                    color: "#ef4444",
                  },
                ].map((feature) => (
                  <div
                    key={feature.title}
                    className="hover-lift animate-fade-up"
                    style={{
                      padding: 20,
                      background: "#151515",
                      border: "1px solid #2a2a2a",
                      borderRadius: 14,
                      transition:
                        "all 0.25s cubic-bezier(0.16,1,0.3,1)",
                    }}
                  >
                    <feature.icon
                      style={{
                        width: 20,
                        height: 20,
                        color: feature.color,
                        marginBottom: 12,
                      }}
                    />
                    <p
                      style={{
                        fontSize: 13,
                        fontWeight: 700,
                        color: "#e5e5e5",
                        marginBottom: 6,
                      }}
                    >
                      {feature.title}
                    </p>
                    <p
                      style={{
                        fontSize: 12,
                        color: "#666",
                        lineHeight: 1.5,
                      }}
                    >
                      {feature.desc}
                    </p>
                  </div>
                ))}
              </div>

              <button
                onClick={() => setShowModal(true)}
                style={{
                  marginTop: 32,
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "12px 24px",
                  background: "#22c55e",
                  color: "black",
                  borderRadius: 10,
                  fontSize: 14,
                  fontWeight: 700,
                  border: "none",
                  cursor: "pointer",
                  transition: "all 0.2s ease",
                }}
              >
                <Plus style={{ width: 16, height: 16 }} />
                Create Your First Project
              </button>
            </div>
          ) : (
            /* Project Grid */
            <div
              className="stagger-children"
              style={{
                display: "grid",
                gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
                gap: 16,
              }}
            >
              {projects.map((project) => (
                <Link
                  key={project.id}
                  href={`/projects/${project.id}`}
                  className="hover-glow animate-fade-up"
                  style={{
                    display: "block",
                    padding: 20,
                    background: "#151515",
                    border: "1px solid #2a2a2a",
                    borderRadius: 14,
                    textDecoration: "none",
                    transition:
                      "all 0.25s cubic-bezier(0.16,1,0.3,1)",
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 12,
                      marginBottom: 12,
                    }}
                  >
                    <FolderOpen
                      style={{ width: 18, height: 18, color: "#22c55e" }}
                    />
                    <span
                      style={{
                        fontSize: 14,
                        fontWeight: 700,
                        color: "#e5e5e5",
                      }}
                    >
                      {project.name}
                    </span>
                  </div>
                  <p style={{ fontSize: 12, color: "#555", lineHeight: 1.5 }}>
                    {project.documents?.length || 0} documents ·{" "}
                    {project.conversations?.length || 0} conversations
                  </p>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 4,
                      marginTop: 12,
                      color: "#555",
                      fontSize: 12,
                      fontWeight: 600,
                    }}
                  >
                    Open workspace
                    <ArrowRight style={{ width: 14, height: 14 }} />
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {showModal && (
        <NewProjectModal
          onClose={() => setShowModal(false)}
          onCreate={async (name, prompt) => {
            await addProject(name, prompt);
            setShowModal(false);
            return true;
          }}
        />
      )}
    </>
  );
}
