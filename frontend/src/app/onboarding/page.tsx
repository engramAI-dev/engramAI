"use client";

/**
 * Onboarding page — provider-agnostic integration flow.
 * Fetches providers from GET /api/providers, shows dynamic cards,
 * lets user connect sources and select resources for indexing.
 * v3 "Datasheet / CRT" terminal aesthetic.
 */

import React, { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch } from "@/lib/api";
import { registerJob } from "@/app/(app)/jobs/page";
import {
  V3Tag,
  V3Btn,
  V3TitleBar,
  V3StatusBar,
  V3Hr,
  V3Input,
  EgLogo,
} from "@/components/engram/components";
import { GitHub, Notion } from "@/components/engram/icons";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface Provider {
  id: string;
  name: string;
  auth_type: "oauth" | "token" | "none";
  connected: boolean;
  metadata: Record<string, unknown>;
}

interface GitHubResource {
  id: string;
  name: string;
  full_name: string;
  description: string | null;
  private: boolean;
  language: string | null;
}

interface NotionResource {
  id: string;
  title: string;
  url: string;
  last_edited: string | null;
}

type Resource = GitHubResource | NotionResource;

type IndexingState = "idle" | "indexing" | "done" | "error";

/* ------------------------------------------------------------------ */
/*  Fallback data when API is unavailable                              */
/* ------------------------------------------------------------------ */

const FALLBACK_PROVIDERS: Provider[] = [
  {
    id: "github",
    name: "GitHub",
    auth_type: "oauth",
    connected: true,
    metadata: {},
  },
  {
    id: "notion",
    name: "Notion",
    auth_type: "oauth",
    connected: false,
    metadata: {},
  },
];

/* ------------------------------------------------------------------ */
/*  Provider icon helper                                               */
/* ------------------------------------------------------------------ */

function ProviderIcon({ id, size = 14 }: { id: string; size?: number }) {
  if (id === "github") return <GitHub size={size} />;
  if (id === "notion") return <Notion size={size} />;
  return <span style={{ fontSize: size, fontFamily: "var(--font-mono)" }}>{id[0].toUpperCase()}</span>;
}

/* ------------------------------------------------------------------ */
/*  Resource name helper                                               */
/* ------------------------------------------------------------------ */

function getResourceName(r: Resource): string {
  if ("full_name" in r) return r.full_name;
  return (r as NotionResource).title ?? r.id;
}

function getResourceDescription(r: Resource): string | null {
  if ("description" in r) return r.description;
  if ("url" in r) return (r as NotionResource).url;
  return null;
}

/* ------------------------------------------------------------------ */
/*  Checkbox row                                                       */
/* ------------------------------------------------------------------ */

function CheckRow({
  checked,
  label,
  sub,
  onChange,
}: {
  checked: boolean;
  label: string;
  sub?: string | null;
  onChange: () => void;
}) {
  return (
    <div
      onClick={onChange}
      style={{
        display: "flex",
        alignItems: "center",
        gap: 8,
        padding: "4px 0",
        cursor: "pointer",
        fontFamily: "var(--font-mono)",
        fontSize: 12,
        color: "var(--ink)",
      }}
    >
      <span style={{ color: checked ? "var(--accent)" : "var(--ink-4)" }}>
        [{checked ? "x" : "\u00A0"}]
      </span>
      <span style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
        {label}
      </span>
      {sub && (
        <span
          style={{
            fontSize: 10,
            color: "var(--ink-4)",
            maxWidth: 160,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {sub}
        </span>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Progress bar (block chars)                                         */
/* ------------------------------------------------------------------ */

function BlockProgress({ progress, width = 20 }: { progress: number; width?: number }) {
  const filled = Math.round(progress * width);
  const empty = width - filled;
  return (
    <span style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--accent)" }}>
      {"\u2588".repeat(filled)}
      <span style={{ color: "var(--ink-4)" }}>{"\u2591".repeat(empty)}</span>
      {" "}
      <span style={{ color: "var(--ink-3)" }}>{Math.round(progress * 100)}%</span>
    </span>
  );
}

/* ------------------------------------------------------------------ */
/*  Provider card                                                      */
/* ------------------------------------------------------------------ */

function ProviderCard({
  provider,
  resources,
  selected,
  loadingResources,
  tokenValue,
  onConnect,
  onToggleResource,
  onTokenChange,
  onTokenSubmit,
}: {
  provider: Provider;
  resources: Resource[];
  selected: Set<string>;
  loadingResources: boolean;
  tokenValue: string;
  onConnect: () => void;
  onToggleResource: (id: string) => void;
  onTokenChange: (v: string) => void;
  onTokenSubmit: () => void;
}) {
  const [showTokenInput, setShowTokenInput] = useState(false);

  return (
    <div
      style={{
        border: "1px solid " + (provider.connected ? "var(--accent)" : "var(--ink-4)"),
        background: "var(--surface)",
        padding: 14,
        flex: 1,
        minWidth: 0,
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 8,
          marginBottom: 10,
        }}
      >
        <ProviderIcon id={provider.id} />
        <span style={{ fontSize: 13, fontWeight: 600, fontFamily: "var(--font-mono)" }}>
          {provider.name.toLowerCase()}
        </span>
        <span style={{ flex: 1 }} />
        {provider.connected ? (
          <V3Tag tone="ok">CONNECTED</V3Tag>
        ) : null}
      </div>

      {/* Connected: show resources */}
      {provider.connected && (
        <div style={{ marginBottom: 10 }}>
          {loadingResources ? (
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                color: "var(--ink-4)",
                padding: "8px 0",
              }}
            >
              loading resources...
            </div>
          ) : resources.length === 0 ? (
            <div
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 11,
                color: "var(--ink-4)",
                padding: "8px 0",
              }}
            >
              no resources found
            </div>
          ) : (
            <div style={{ maxHeight: 220, overflowY: "auto" }}>
              {resources.map((r) => (
                <CheckRow
                  key={r.id}
                  checked={selected.has(r.id)}
                  label={getResourceName(r)}
                  sub={getResourceDescription(r)}
                  onChange={() => onToggleResource(r.id)}
                />
              ))}
            </div>
          )}
        </div>
      )}

      {/* Not connected: show connect button or token input */}
      {!provider.connected && (
        <div style={{ marginTop: 4 }}>
          {provider.auth_type === "token" && showTokenInput ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              <V3Input
                value={tokenValue}
                onChange={(e) => onTokenChange(e.target.value)}
                placeholder="paste API token..."
                style={{ width: "100%", fontSize: 11 }}
              />
              <div style={{ display: "flex", gap: 6 }}>
                <V3Btn
                  variant="acc"
                  size="sm"
                  onClick={onTokenSubmit}
                  disabled={!tokenValue.trim()}
                  style={{ flex: 1 }}
                >
                  save token
                </V3Btn>
                <V3Btn size="sm" onClick={() => setShowTokenInput(false)}>
                  cancel
                </V3Btn>
              </div>
            </div>
          ) : (
            <V3Btn
              variant="acc"
              size="sm"
              onClick={() => {
                if (provider.auth_type === "token") {
                  setShowTokenInput(true);
                } else {
                  onConnect();
                }
              }}
              style={{ width: "100%" }}
            >
              connect {provider.name.toLowerCase()}
            </V3Btn>
          )}
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function OnboardingPage() {
  const router = useRouter();

  const [providers, setProviders] = useState<Provider[]>([]);
  const [resources, setResources] = useState<Record<string, Resource[]>>({});
  const [selected, setSelected] = useState<Record<string, Set<string>>>({});
  const [loadingProviders, setLoadingProviders] = useState(true);
  const [loadingResources, setLoadingResources] = useState<Record<string, boolean>>({});
  const [tokenInputs, setTokenInputs] = useState<Record<string, string>>({});
  const [indexingState, setIndexingState] = useState<IndexingState>("idle");
  const [indexingProgress, setIndexingProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);

  /* ---- Fetch providers on mount ---- */
  useEffect(() => {
    apiFetch<Provider[]>("/api/providers")
      .then((data) => {
        const list = Array.isArray(data) ? data : FALLBACK_PROVIDERS;
        setProviders(list);
        setLoadingProviders(false);

        // For each connected provider, fetch resources
        for (const p of list) {
          if (p.connected) {
            fetchResources(p.id);
          }
        }
      })
      .catch(() => {
        setProviders(FALLBACK_PROVIDERS);
        setLoadingProviders(false);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  /* ---- Fetch resources for a provider ---- */
  const fetchResources = useCallback((providerId: string) => {
    setLoadingResources((prev) => ({ ...prev, [providerId]: true }));

    apiFetch<Resource[]>(`/api/providers/${providerId}/resources`)
      .then((data) => {
        const list = Array.isArray(data) ? data : [];
        setResources((prev) => ({ ...prev, [providerId]: list }));
        setLoadingResources((prev) => ({ ...prev, [providerId]: false }));
      })
      .catch(() => {
        setResources((prev) => ({ ...prev, [providerId]: [] }));
        setLoadingResources((prev) => ({ ...prev, [providerId]: false }));
      });
  }, []);

  /* ---- Toggle resource selection ---- */
  const toggleResource = useCallback((providerId: string, resourceId: string) => {
    setSelected((prev) => {
      const current = new Set(prev[providerId] ?? []);
      if (current.has(resourceId)) {
        current.delete(resourceId);
      } else {
        current.add(resourceId);
      }
      return { ...prev, [providerId]: current };
    });
  }, []);

  /* ---- Connect a provider (OAuth) ---- */
  const connectProvider = useCallback((provider: Provider) => {
    apiFetch<{ redirect_url?: string; connected?: boolean }>(
      `/api/providers/${provider.id}/connect`,
      { method: "POST" },
    )
      .then((data) => {
        if (data.redirect_url) {
          // OAuth flow — redirect to provider
          window.location.href = data.redirect_url;
        } else if (data.connected) {
          // Token/API key fallback — already connected
          setProviders((prev) =>
            prev.map((p) => (p.id === provider.id ? { ...p, connected: true } : p)),
          );
          fetchResources(provider.id);
        }
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to connect");
      });
  }, []);

  /* ---- Submit token for a provider ---- */
  const submitToken = useCallback((providerId: string) => {
    const token = tokenInputs[providerId]?.trim();
    if (!token) return;

    apiFetch<{ connected: boolean }>(`/api/providers/${providerId}/token`, {
      method: "POST",
      body: JSON.stringify({ token }),
    })
      .then(() => {
        setProviders((prev) =>
          prev.map((p) => (p.id === providerId ? { ...p, connected: true } : p)),
        );
        setTokenInputs((prev) => ({ ...prev, [providerId]: "" }));
        fetchResources(providerId);
      })
      .catch((err) => {
        setError(err instanceof Error ? err.message : "Failed to save token");
      });
  }, [tokenInputs, fetchResources]);

  /* ---- Start indexing ---- */
  const startIndexing = useCallback(() => {
    const jobs: Promise<{ job_id: string; status: string }>[] = [];

    for (const provider of providers) {
      const sel = selected[provider.id];
      if (!sel || sel.size === 0) continue;

      const providerResources = resources[provider.id] ?? [];
      const selectedResources = providerResources.filter((r) => sel.has(r.id));

      if (provider.id === "github") {
        for (const r of selectedResources) {
          const fullName = "full_name" in r ? r.full_name : r.id;
          jobs.push(
            apiFetch<{ job_id: string; status: string }>("/api/ingest/github", {
              method: "POST",
              body: JSON.stringify({ repo_url: `https://github.com/${fullName}` }),
            }).then((data) => {
              registerJob(data.job_id, fullName, "git");
              return data;
            }),
          );
        }
      } else if (provider.id === "notion") {
        for (const r of selectedResources) {
          const title = "title" in r ? r.title : r.id;
          jobs.push(
            apiFetch<{ job_id: string; status: string }>("/api/ingest/notion", {
              method: "POST",
              body: JSON.stringify({ page_id: r.id }),
            }).then((data) => {
              registerJob(data.job_id, title, "ntn");
              return data;
            }),
          );
        }
      } else {
        // Generic provider — post each resource
        for (const r of selectedResources) {
          jobs.push(
            apiFetch<{ job_id: string; status: string }>(`/api/ingest/${provider.id}`, {
              method: "POST",
              body: JSON.stringify({ resource_id: r.id }),
            }),
          );
        }
      }
    }

    if (jobs.length === 0) return;

    setIndexingState("indexing");
    setIndexingProgress(0);

    // Simulate progress while waiting
    let progressInterval: ReturnType<typeof setInterval> | null = null;
    progressInterval = setInterval(() => {
      setIndexingProgress((prev) => {
        if (prev >= 0.9) {
          if (progressInterval) clearInterval(progressInterval);
          return 0.9;
        }
        return prev + 0.1;
      });
    }, 400);

    Promise.allSettled(jobs)
      .then(() => {
        if (progressInterval) clearInterval(progressInterval);
        setIndexingProgress(1);
        setIndexingState("done");
        localStorage.setItem("engram_onboarded", "true");
        setTimeout(() => {
          router.replace("/");
        }, 800);
      })
      .catch(() => {
        if (progressInterval) clearInterval(progressInterval);
        setIndexingState("error");
        setError("Some indexing jobs failed. You can retry from the connections page.");
        // Still mark onboarded so user can proceed
        localStorage.setItem("engram_onboarded", "true");
      });
  }, [providers, selected, resources, router]);

  /* ---- Computed ---- */
  const totalSelected = Object.values(selected).reduce((sum, s) => sum + s.size, 0);
  const connectedCount = providers.filter((p) => p.connected).length;
  const canProceed = totalSelected > 0 && indexingState === "idle";

  return (
    <div
      className="v3-screen v3-scan"
      data-theme="dark"
      data-accent="phosphor"
      style={{
        alignItems: "center",
        justifyContent: "center",
        padding: 24,
      }}
    >
      <div style={{ width: 640, maxWidth: "100%" }}>
        <div className="v3-frame" style={{ height: "auto" }}>
          <V3TitleBar
            path='engram@core:~/setup$ connect'
            right={
              <button
                onClick={() => router.push("/")}
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 10,
                  color: "var(--ink-4)",
                  background: "transparent",
                  border: "none",
                  cursor: "pointer",
                }}
              >
                skip
              </button>
            }
          />

          <div style={{ padding: 24 }}>
            {/* Logo header */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                marginBottom: 16,
              }}
            >
              <EgLogo size={18} />
              <span
                style={{
                  fontSize: 15,
                  fontWeight: 600,
                  letterSpacing: "0.04em",
                  fontFamily: "var(--font-mono)",
                }}
              >
                engram
              </span>
              <span className="v3-marg">setup</span>
            </div>

            <span
              className="v3-cap"
              style={{ marginBottom: 12, display: "block" }}
            >
              connect your sources
            </span>

            {/* Error */}
            {error && (
              <div
                style={{
                  padding: "8px 12px",
                  marginBottom: 12,
                  border: "1px solid var(--err, #f44)",
                  fontFamily: "var(--font-mono)",
                  fontSize: 11,
                  color: "var(--err, #f44)",
                }}
              >
                err: {error}
              </div>
            )}

            {/* Loading providers */}
            {loadingProviders ? (
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                  color: "var(--ink-4)",
                  padding: "24px 0",
                  textAlign: "center",
                }}
              >
                fetching providers...
              </div>
            ) : (
              <>
                {/* Provider cards */}
                <div
                  style={{
                    display: "grid",
                    gridTemplateColumns: providers.length > 1 ? "1fr 1fr" : "1fr",
                    gap: 12,
                  }}
                >
                  {providers.map((p) => (
                    <ProviderCard
                      key={p.id}
                      provider={p}
                      resources={resources[p.id] ?? []}
                      selected={selected[p.id] ?? new Set<string>()}
                      loadingResources={loadingResources[p.id] ?? false}
                      tokenValue={tokenInputs[p.id] ?? ""}
                      onConnect={() => connectProvider(p)}
                      onToggleResource={(rid) => toggleResource(p.id, rid)}
                      onTokenChange={(v) =>
                        setTokenInputs((prev) => ({ ...prev, [p.id]: v }))
                      }
                      onTokenSubmit={() => submitToken(p.id)}
                    />
                  ))}
                </div>

                <V3Hr />

                {/* Indexing state */}
                {indexingState === "indexing" && (
                  <div style={{ marginBottom: 12, textAlign: "center" }}>
                    <BlockProgress progress={indexingProgress} width={30} />
                    <div
                      style={{
                        fontFamily: "var(--font-mono)",
                        fontSize: 11,
                        color: "var(--ink-3)",
                        marginTop: 6,
                      }}
                    >
                      indexing {totalSelected} resource{totalSelected !== 1 ? "s" : ""}...
                    </div>
                  </div>
                )}

                {indexingState === "done" && (
                  <div
                    style={{
                      fontFamily: "var(--font-mono)",
                      fontSize: 12,
                      color: "var(--accent)",
                      textAlign: "center",
                      marginBottom: 12,
                    }}
                  >
                    indexing started. redirecting...
                  </div>
                )}

                {/* Start indexing button */}
                {indexingState === "idle" && (
                  <V3Btn
                    variant={canProceed ? "acc" : undefined}
                    onClick={startIndexing}
                    disabled={!canProceed}
                    style={{
                      width: "100%",
                      height: 32,
                      justifyContent: "center",
                      opacity: canProceed ? 1 : 0.5,
                    }}
                  >
                    start indexing {"\u2192"}
                  </V3Btn>
                )}

                {indexingState === "error" && (
                  <V3Btn
                    variant="acc"
                    onClick={() => {
                      localStorage.setItem("engram_onboarded", "true");
                      router.replace("/");
                    }}
                    style={{
                      width: "100%",
                      height: 32,
                      justifyContent: "center",
                    }}
                  >
                    continue to workspace {"\u2192"}
                  </V3Btn>
                )}

                {totalSelected === 0 && indexingState === "idle" && (
                  <>
                    <div
                      className="v3-marg"
                      style={{ textAlign: "center", marginTop: 8 }}
                    >
                      {`// select resources to index, or skip`}
                    </div>
                    <button
                      onClick={() => {
                        localStorage.setItem("engram_onboarded", "true");
                        router.replace("/");
                      }}
                      style={{
                        display: "block",
                        margin: "8px auto 0",
                        background: "transparent",
                        border: "none",
                        color: "var(--ink-4)",
                        fontFamily: "var(--font-mono)",
                        fontSize: 11,
                        cursor: "pointer",
                      }}
                    >
                      {"[ skip setup ]"}
                    </button>
                  </>
                )}
              </>
            )}
          </div>

          <V3StatusBar
            items={[
              <span key="status">online</span>,
              `${connectedCount} provider${connectedCount !== 1 ? "s" : ""}`,
              `${totalSelected} selected`,
            ]}
          />
        </div>
      </div>
    </div>
  );
}
