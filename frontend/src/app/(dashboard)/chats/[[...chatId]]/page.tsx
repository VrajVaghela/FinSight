import ChatContainer from "@/components/ChatContainer";
import DebugPanel from "@/components/debug/DebugPanel";

export default function StandaloneChatPage() {
  return (
    <div style={{ display: "flex", height: "100%", width: "100%", background: "#0a0a0a" }}>
      {/* Main Chat Area */}
      <div style={{ flex: 1, position: "relative", minWidth: 0 }}>
        <ChatContainer projectId="standalone" />
      </div>
    </div>
  );
}
