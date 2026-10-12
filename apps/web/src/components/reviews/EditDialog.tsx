"use client";

import { useState } from "react";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useEditReview, ReviewItem } from "@/lib/hooks/use-reviews";
import { Message } from "@/lib/hooks/use-messages";
import { toast } from "sonner";

export function EditDialog({
  open,
  onOpenChange,
  item,
  message,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  item: ReviewItem;
  message: Message;
}) {
  const [subject, setSubject] = useState(message.subject || "");
  const [body, setBody] = useState(message.body_text || "");
  const edit = useEditReview();

  async function onSave() {
    try {
      await edit.mutateAsync({ id: item.id, subject, bodyText: body });
      toast.success("Сохранено");
      onOpenChange(false);
    } catch {
      toast.error("Ошибка сохранения");
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Редактирование письма</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium">Тема</label>
            <Input value={subject} onChange={(e) => setSubject(e.target.value)} />
          </div>
          <div>
            <label className="text-sm font-medium">Тело письма</label>
            <textarea value={body} onChange={(e) => setBody(e.target.value)}
              className="w-full border rounded p-3 text-sm font-mono" rows={16} />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Отмена</Button>
          <Button onClick={onSave} disabled={edit.isPending}>
            {edit.isPending ? "Сохранение..." : "Сохранить"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
