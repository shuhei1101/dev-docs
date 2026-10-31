import { type ReactNode, createContext, useContext, useState } from "react";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/shared/components/ui/alert-dialog";

export type ConfirmRequest = {
  title: string;
  description: ReactNode;
  confirmLabel: string;
  destructive: boolean;
};

type Pending = { request: ConfirmRequest; resolve: (ok: boolean) => void };
type Confirm = (request: ConfirmRequest) => Promise<boolean>;

const ConfirmContext = createContext<Confirm | null>(null);

/** `useConfirmDialog` から開く確認のダイアログを 1 つだけ持つ */
export const ConfirmDialogProvider = ({
  children,
}: {
  children: ReactNode;
}) => {
  const [pending, setPending] = useState<Pending | null>(null);

  const confirm: Confirm = (request) =>
    new Promise<boolean>((resolve) => {
      setPending({ request, resolve });
    });

  const close = (ok: boolean) => {
    pending?.resolve(ok);
    setPending(null);
  };

  return (
    <ConfirmContext.Provider value={confirm}>
      {children}
      <AlertDialog
        open={pending !== null}
        onOpenChange={(open) => !open && close(false)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{pending?.request.title}</AlertDialogTitle>
            <AlertDialogDescription>
              {pending?.request.description}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>キャンセル</AlertDialogCancel>
            <AlertDialogAction
              variant={pending?.request.destructive ? "destructive" : "default"}
              onClick={() => close(true)}
            >
              {pending?.request.confirmLabel}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </ConfirmContext.Provider>
  );
};

/** 確認のダイアログを開き、確定なら true を返す関数を返す */
export const useConfirmDialog = (): Confirm => {
  const confirm = useContext(ConfirmContext);
  if (confirm === null)
    throw new Error("ConfirmDialogProvider の中で使ってください");
  return confirm;
};
