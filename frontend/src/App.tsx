import { useEffect, useState } from "react";
import { api } from "./api";
import type { Config, Measured } from "./api";
import { ErrorBox, Skeleton } from "./components/ui";
import { JudgePage } from "./pages/Judge";
import { PlaygroundPage } from "./pages/Playground";
import { RoiPage } from "./pages/Roi";

const TABS = [
  { key: "roi", label: "ROI calculator" },
  { key: "playground", label: "Playground" },
  { key: "judge", label: "False-hit judge" },
] as const;
type Tab = (typeof TABS)[number]["key"];

const tabFromHash = (): Tab => {
  const h = window.location.hash.replace("#", "");
  return (TABS.some((t) => t.key === h) ? h : "roi") as Tab;
};

export function App() {
  const [tab, setTab] = useState<Tab>(tabFromHash);
  const [config, setConfig] = useState<Config | null>(null);
  const [measured, setMeasured] = useState<Measured | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [threshold, setThreshold] = useState(0.75);

  const load = async () => {
    setError(null);
    try {
      const [c, m] = await Promise.all([api.config(), api.measured()]);
      setConfig(c); setMeasured(m); setThreshold(c.threshold);
    } catch (e) { setError(e); }
  };
  useEffect(() => { load(); }, []);
  useEffect(() => {
    const on = () => setTab(tabFromHash());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);

  return (
    <div className="app">
      <header className="top">
        <div>
          <h1>Semantic cache on Lakebase</h1>
          <p className="muted">
            {config
              ? <>{config.llm_endpoint} · {config.embedding_endpoint} · {config.backend} on {config.lakebase_instance} · {config.entries} entries</>
              : "Loading configuration…"}
          </p>
        </div>
        <nav className="tabs" role="tablist">
          {TABS.map((t) => (
            <a key={t.key} href={`#${t.key}`} role="tab" aria-selected={tab === t.key}
               className={tab === t.key ? "active" : ""}>{t.label}</a>
          ))}
        </nav>
      </header>
      <main>
        {error !== null && <ErrorBox error={error} onRetry={load} />}
        {!error && (!config || !measured) && <><Skeleton height={90} /><Skeleton height={320} /></>}
        {config && measured && (
          <>
            {tab === "roi" && <RoiPage config={config} measured={measured} threshold={threshold} setThreshold={setThreshold} />}
            {tab === "playground" && <PlaygroundPage config={config} measured={measured} threshold={threshold} setThreshold={setThreshold} />}
            {tab === "judge" && <JudgePage />}
          </>
        )}
      </main>
    </div>
  );
}
