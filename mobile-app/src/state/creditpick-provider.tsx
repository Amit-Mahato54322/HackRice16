import {
  createContext,
  PropsWithChildren,
  useContext,
  useState,
  useEffect,
  useRef,
} from "react";
import type { Purchase } from "@/domain/models";
import { services as defaultServices } from "@/services";
import type {
  CreditPickServices,
  Recommendation,
  WalletSnapshot,
} from "@/services/contracts";
type CreditPickState = {
  purchase: Purchase;
  flowId: number;
  updatePurchase: (patch: Partial<Purchase>) => void;
  reset: () => void;
  threshold: number;
  setThreshold: (value: number) => void;
  services: CreditPickServices;
  wallet: WalletSnapshot | null;
  walletError: string | null;
  reloadWallet: () => void;
  recommendation: Recommendation | null;
  compare: (signal: AbortSignal) => Promise<void>;
};
const CreditPickContext = createContext<CreditPickState | null>(null);
export function CreditPickProvider({
  children,
  services = defaultServices,
}: PropsWithChildren<{ services?: CreditPickServices }>) {
  const [purchase, setPurchase] = useState<Purchase>({
    ...services.initialPurchase,
  });
  const [threshold, setThreshold] = useState(30);
  const [flowId, setFlowId] = useState(0);
  const [wallet, setWallet] = useState<WalletSnapshot | null>(null);
  const [walletError, setWalletError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [recommendation, setRecommendation] = useState<Recommendation | null>(
    null,
  );
  const revision = useRef(0);
  useEffect(() => {
    const request = new AbortController();
    setWalletError(null);
    void services.wallet
      .get(request.signal)
      .then((value) => {
        if (!request.signal.aborted) setWallet(value);
      })
      .catch(() => {
        if (!request.signal.aborted)
          setWalletError("Unable to load your wallet. Please try again.");
      });
    return () => request.abort();
  }, [services, reload]);
  function invalidate() {
    revision.current += 1;
    setRecommendation(null);
  }
  return (
    <CreditPickContext.Provider
      value={{
        purchase,
        flowId,
        updatePurchase: (patch) => {
          invalidate();
          setPurchase((current) => ({ ...current, ...patch }));
        },
        reset: () => {
          setFlowId((value) => value + 1);
          invalidate();
          setPurchase({ ...services.initialPurchase });
        },
        threshold,
        setThreshold: (value) => {
          invalidate();
          setThreshold(value);
        },
        services,
        wallet,
        walletError,
        reloadWallet: () => setReload((value) => value + 1),
        recommendation,
        compare: async (signal) => {
          const requestedRevision = revision.current;
          const result = await services.recommendations.compare(
            { ...purchase },
            threshold,
            signal,
          );
          if (signal.aborted || revision.current !== requestedRevision)
            throw new Error("Purchase changed. Please compare again.");
          setRecommendation(result);
        },
      }}
    >
      {children}
    </CreditPickContext.Provider>
  );
}
export function useCreditPick() {
  const state = useContext(CreditPickContext);
  if (!state) throw new Error("useCreditPick requires CreditPickProvider");
  return state;
}
