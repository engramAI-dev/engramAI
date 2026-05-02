"use client";

import React from "react";
import {
  V3TitleBar,
  V3StatusBar,
  V3Hr,
  EgLogo,
} from "@/components/engram/components";
import { getLoginUrl } from "@/lib/auth";

/* ------------------------------------------------------------------ */
/*  Page                                                               */
/* ------------------------------------------------------------------ */

export default function LoginPage() {
  function handleGithub() {
    window.location.href = getLoginUrl();
  }

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
      <div style={{ width: 460 }}>
        <div className="v3-frame" style={{ height: "auto" }}>
          <V3TitleBar
            path="engram@core:~$ login --github"
            right={<span style={{ color: "var(--accent)" }}>{"\u25CF"}</span>}
          />

          <div style={{ padding: 24 }}>
            {/* logo */}
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
                }}
              >
                engram
              </span>
            </div>

            {/* system info */}
            <pre
              style={{
                margin: 0,
                fontSize: 11,
                lineHeight: 1.7,
                color: "var(--ink-3)",
              }}
            >
{`engram v0.1 · memory core
loaded modules: chat retrieval ingestion outputs
status:        operational · us-west-2
auth required: github oauth (read:user, repo:read)`}
            </pre>

            <V3Hr />

            {/* prompt */}
            <div
              className="v3-prompt"
              style={{ marginBottom: 14, fontSize: 13, color: "var(--ink)" }}
            >
              <span style={{ color: "var(--ink-3)" }}>connect</span>
            </div>

            {/* github button */}
            <button
              className="v3-btn"
              data-variant="acc"
              onClick={handleGithub}
              style={{
                width: "100%",
                height: 32,
                justifyContent: "center",
              }}
            >
              continue with github {"\u2192"}
            </button>
          </div>

          <V3StatusBar
            items={[
              <span key="online">
                <span style={{ color: "var(--accent)" }}>{"\u25CF"}</span> ONLINE
              </span>,
              "us-west-2",
              "TLS 1.3",
            ]}
          />
        </div>

        {/* legal */}
        <div
          style={{
            textAlign: "center",
            marginTop: 12,
            color: "var(--ink-4)",
            fontSize: 10.5,
          }}
        >
          {`// by continuing you agree to `}
          <span style={{ color: "var(--ink)" }}>terms</span> &amp;{" "}
          <span style={{ color: "var(--ink)" }}>privacy</span>
        </div>
      </div>
    </div>
  );
}
