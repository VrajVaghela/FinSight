"use client";

import { use } from "react";
import Header from "@/components/Header";
import FileUploadZone from "@/components/FileUploadZone";

export default function ProjectDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);

  return (
    <>
      <Header projectName={`Project ${id}`} />
      <div
        className="animate-fade-up"
        style={{
          flex: 1,
          overflow: "auto",
          padding: 32,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <FileUploadZone projectId={id} />
      </div>
    </>
  );
}
