import { Badge } from "@/components/ui/badge";
import { ExternalLink, AlertTriangle } from "lucide-react";

type FactualClaim = {
  claim: string;
  evidence_url: string | null;
  confidence: number;
  is_hypothesis: boolean;
};

export function FactualClaimsList({ claims }: { claims: FactualClaim[] }) {
  if (!claims || claims.length === 0) return null;
  return (
    <div className="bg-white border rounded-lg p-4">
      <div className="font-medium mb-3">Утверждения в письме</div>
      <div className="space-y-2">
        {claims.map((claim, i) => (
          <div key={i} className="flex items-start gap-3 text-sm">
            {claim.is_hypothesis ? (
              <AlertTriangle className="h-4 w-4 text-amber-500 mt-0.5 flex-shrink-0" />
            ) : (
              <div className="h-4 w-4 rounded-full bg-green-500 mt-0.5 flex-shrink-0" />
            )}
            <div className="flex-1">
              <div>{claim.claim}</div>
              <div className="flex items-center gap-2 mt-1">
                <span className="text-xs text-slate-500">
                  confidence: {(claim.confidence * 100).toFixed(0)}%
                </span>
                {claim.is_hypothesis && (
                  <Badge className="bg-amber-100 text-amber-700 text-xs">гипотеза</Badge>
                )}
                {claim.evidence_url && (
                  <a href={claim.evidence_url} target="_blank" rel="noopener"
                    className="text-xs text-blue-600 hover:underline flex items-center gap-1">
                    источник <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
