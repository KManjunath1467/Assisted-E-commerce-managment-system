import { User } from "lucide-react";
import type { UserMessage } from "@/lib/types";

interface Props {
  message: UserMessage;
}

export function MessageBubble({ message }: Props) {
  const time = new Date(message.timestamp).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="flex w-full items-end justify-end gap-2">
      <div className="flex max-w-[75%] flex-col items-end gap-1">
        <div className="rounded-2xl rounded-br-sm bg-primary px-4 py-2.5 text-sm text-primary-foreground">
          <p className="whitespace-pre-wrap break-words leading-relaxed">
            {message.text}
          </p>
        </div>
        <span className="pr-1 text-[0.7rem] font-medium text-muted-foreground">
          {time}
        </span>
      </div>
      <div className="mb-5 flex size-8 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground">
        <User className="size-4" />
      </div>
    </div>
  );
}
