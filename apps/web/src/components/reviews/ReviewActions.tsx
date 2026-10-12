"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { useApproveReview, useRejectReview, ReviewItem } from "@/lib/hooks/use-reviews";
import { toast } from "sonner";
import { useRouter } from "next/navigation";
import { Check, X } from "lucide-react";

export function ReviewActions({ item }: { item: ReviewItem }) {
  const router = useRouter();
  const approve = useApproveReview();
  const reject = useRejectReview();
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");

  async function onApprove() {
    try {
      await approve.mutateAsync({ id: item.id });
      toast.success("Одобрено");
      router.push("/reviews");
    } catch {
      toast.error("Ошибка одобрения");
    }
  }

  async function onReject() {
    if (!reason.trim()) {
      toast.error("Укажите причину");
      return;
    }
    try {
      await reject.mutateAsync({ id: item.id, reason });
      toast.success("Отклонено");
      router.push("/reviews");
    } catch {
      toast.error("Ошибка отклонения");
    }
  }

  if (item.status !== "pending") {
    return (
      <div className="bg-white border rounded-lg p-4 text-sm text-slate-500">
        Статус: <strong>{item.status}</strong>
        {item.reviewed_by ? <> · ревьюер: {item.reviewed_by}</> : null}
      </div>
    );
  }

  return (
    <div className="bg-white border rounded-lg p-4 sticky bottom-4">
      {!rejecting ? (
        <div className="flex gap-3">
          <Button onClick={onApprove} disabled={approve.isPending} className="flex-1">
            <Check className="h-4 w-4 mr-2" />
            {approve.isPending ? "Отправка..." : "Одобрить и отправить"}
          </Button>
          <Button variant="outline" onClick={() => setRejecting(true)} className="flex-1">
            <X className="h-4 w-4 mr-2" /> Отклонить
          </Button>
        </div>
      ) : (
        <div className="space-y-3">
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="Причина отклонения..."
            className="w-full border rounded p-2 text-sm"
            rows={3}
          />
          <div className="flex gap-3">
            <Button variant="destructive" onClick={onReject} disabled={reject.isPending}>
              {reject.isPending ? "Отклонение..." : "Подтвердить отклонение"}
            </Button>
            <Button variant="outline" onClick={() => setRejecting(false)}>Отмена</Button>
          </div>
        </div>
      )}
    </div>
  );
}
