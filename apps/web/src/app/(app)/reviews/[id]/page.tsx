"use client";

import { useReview } from "@/lib/hooks/use-reviews";
import { ReviewDetail } from "@/components/reviews/ReviewDetail";
import { use } from "react";

export default function ReviewDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data, isLoading } = useReview(id);

  if (isLoading) return <div className="text-slate-500">Загрузка...</div>;
  if (!data) return <div className="text-slate-500">Не найдено</div>;

  return <ReviewDetail item={data} />;
}
