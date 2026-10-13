import { Message } from "@/lib/hooks/use-messages";
import { MarkdownLite } from "@/components/shared/MarkdownLite";

export function MessagePreview({ message }: { message: Message }) {
  return (
    <div className="bg-white border rounded-lg p-6">
      <div className="text-sm text-slate-500 border-b pb-3 mb-4 space-y-1">
        <div><strong>От:</strong> {message.sender?.from_name} &lt;{message.sender?.from_email}&gt;</div>
        <div><strong>Кому:</strong> {message.recipient_snapshot?.email}</div>
        <div><strong>Тема:</strong> {message.subject}</div>
      </div>
      <div className="text-slate-800"><MarkdownLite text={message.body_text} /></div>
    </div>
  );
}
