"use client";

interface MessageProps {
  role: "user" | "assistant";
  content: string;
  isRefusal?: boolean;
}

export default function Message({ role, content, isRefusal }: MessageProps) {
  const isUser = role === "user";

  // Highlight citation markers [n]
  const renderContent = (text: string) => {
    const parts = text.split(/(\[\d+\])/g);
    return parts.map((part, i) => {
      if (/^\[\d+\]$/.test(part)) {
        return (
          <span
            key={i}
            className="inline-flex items-center justify-center px-1.5 py-0.5 text-xs font-semibold bg-blue-100 text-blue-700 rounded cursor-pointer hover:bg-blue-200"
          >
            {part}
          </span>
        );
      }
      return <span key={i}>{part}</span>;
    });
  };

  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[80%] px-4 py-3 rounded-lg ${
          isUser
            ? "bg-blue-600 text-white"
            : isRefusal
            ? "bg-amber-50 border border-amber-200 text-amber-800"
            : "bg-gray-100 text-gray-900"
        }`}
      >
        {isRefusal && (
          <div className="flex items-center gap-2 mb-2 text-sm font-medium text-amber-600">
            <span>Insufficient evidence</span>
          </div>
        )}
        <div className="whitespace-pre-wrap leading-relaxed">
          {isUser ? content : renderContent(content)}
        </div>
      </div>
    </div>
  );
}
