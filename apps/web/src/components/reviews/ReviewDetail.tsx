"use client";

import { useState } from "react";
import { MessagePreview } from "./MessagePreview";
import { FactualClaimsList } from "./FactualClaimsList";
import { ReviewActions } from "./ReviewActions";
import { EditDialog } from "./EditDialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ReviewItem } from "@/lib/hooks/use-reviews";
import { useMessage } from "@/lib/hooks/use-messages";
import { Pencil } from "lucide-react";

export function ReviewDetail({ item }: { item: ReviewItem }) {
  const [editOpen, setEditOpen] = useState(false);
  const { data: message, isLoading } = useMessage(item.message_id);

  if (isLoading) return <div className="text-slate-500">Загрузка письма...</div>;
  if (!message) return <div className="text-slate-500">Письмо не найдено</div>;

  const warnings = item.snapshot?.warnings || message.personalization?.warnings || [];

  return (
    <div className="max-w-4xl space-y-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{message.subject || "(без темы)"}</h1>
          <div className="flex items-center gap-2 mt-2">
            <Badge>{item.channel}</Badge>
            <Badge variant="outline">{item.priority}</Badge>
            {message.personalization?.template_id && (
              <Badge variant="outline">
                {message.personalization.template_id}:{message.personalization.template_version}
              </Badge>
            )}
          </div>
        </div>
        <Button variant="outline" onClick={() => setEditOpen(true)}>
          <Pencil className="h-4 w-4 mr-2" /> Редактировать
        </Button>
      </div>

      {warnings.length > 0 && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
          <div className="font-medium text-amber-800 mb-2">Предупреждения</div>
          <ul className="text-sm text-amber-700 space-y-1">
            {warnings.map((w, i) => <li key={i}>• {w}</li>)}
          </ul>
        </div>
      )}

      <MessagePreview message={message} />
      <FactualClaimsList claims={message.personalization?.factual_claims || []} />

      <div className="grid grid-cols-2 gap-4 text-sm">
        <div className="bg-white border rounded-lg p-4">
          <div className="font-medium mb-2">Получатель</div>
          <div>{message.recipient_snapshot?.full_name}</div>
          <div className="text-slate-500">{message.recipient_snapshot?.position}</div>
          <div className="text-slate-500">{message.recipient_snapshot?.company_name}</div>
          <div className="text-slate-500 mt-2">{message.recipient_snapshot?.email}</div>
        </div>
        <div className="bg-white border rounded-lg p-4">
          <div className="font-medium mb-2">Отправитель</div>
          <div>{message.sender?.from_name}</div>
          <div className="text-slate-500">{message.sender?.from_email}</div>
          {message.sender?.signature && (
            <div className="text-slate-500 mt-2 whitespace-pre-line">{message.sender.signature}</div>
          )}
        </div>
      </div>

      <ReviewActions item={item} />
      <EditDialog open={editOpen} onOpenChange={setEditOpen} item={item} message={message} />
    </div>
  );
}
