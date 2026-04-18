"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Unhandled error:", error);
  }, [error]);

  return (
    <div className="flex min-h-screen items-center justify-center p-8">
      <Card className="w-full max-w-sm">
        <CardContent className="flex flex-col items-center gap-4 pt-6 text-center">
          <h2 className="text-lg font-semibold text-foreground">
            Something went wrong
          </h2>
          <p className="text-sm text-muted-foreground">
            {error.message || "An unexpected error occurred."}
          </p>
          <Button onClick={reset} size="sm">
            Try again
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
