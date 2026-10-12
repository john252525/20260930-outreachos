"use client";

import { useReviews } from "@/lib/hooks/use-reviews";
import { ReviewList } from "@/components/reviews/ReviewList";
import { ReviewFilters } from "@/components/reviews/ReviewFilters";
import { useState } from "react";

export default function ReviewsPage() {
  const [filters, setFilters] = useState<{ status?: string; priority?: string }>({ status: "pending" });
  const { data, isLoading, error } = useReviews(filters);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Reviews</h1>
        <p className="text-sm text-slate-500 mt-1">Письма, ожидающие проверки перед отправкой</p>
      </div>
      <ReviewFilters filters={filters} onChange={setFilters} />
      {isLoading && <div className="text-slate-500">Загрузка...</div>}
      {error && <div className="text-red-600">Ошибка загрузки</div>}
      {data && <ReviewList items={data} />}
    </div>
  );
}
