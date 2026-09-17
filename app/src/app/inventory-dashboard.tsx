"use client";

import { useEffect, useState } from "react";

import type { RepositorySummary } from "@/github/client";
import type { ImpactReport } from "@/types/impact";
import type { Dependency, Inventory } from "@/types/inventory";

function Status({ value }: { value: Dependency["status"] }) {
  return <span className={`status status-${value}`}>{value}</span>;
}

export function InventoryDashboard({
  initialInventory,
  initialImpacts,
}: {
  initialInventory: Inventory;
  initialImpacts: ImpactReport;
}) {
  const [inventory, setInventory] = useState(initialInventory);
  const [impacts, setImpacts] = useState(initialImpacts);
  const [repositories, setRepositories] = useState<RepositorySummary[]>([]);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [indexing, setIndexing] = useState<string | null>(null);

  useEffect(() => {
    void fetch("/api/github/repositories")
      .then(async (response) => {
        if (!response.ok) throw new Error((await response.json()).error ?? "Could not load repositories");
        return response.json() as Promise<RepositorySummary[]>;
      })
      .then(setRepositories)
      .catch((error: Error) => setConnectionError(error.message));
  }, []);

  async function indexRepository(repository: RepositorySummary) {
    setIndexing(repository.fullName);
    setConnectionError(null);
    try {
      const response = await fetch("/api/github/repositories/index", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fullName: repository.fullName, ref: repository.defaultBranch }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error ?? "Could not index repository");
      setInventory(data as Inventory);
      const impactResponse = await fetch("/api/impacts");
      if (impactResponse.ok) setImpacts(await impactResponse.json() as ImpactReport);
    } catch (error) {
      setConnectionError(error instanceof Error ? error.message : "Could not index repository");
    } finally {
      setIndexing(null);
    }
  }

  const affected = impacts.impacts.filter((impact) => impact.matches.length > 0);

  return (
    <main>
      <header>
        <div className="topline">
          <div className="wordmark"><span>A</span> Avert</div>
          <a className="connect" href="/api/github/connect">Connect GitHub</a>
        </div>
        <div className="eyebrow">API dependency intelligence</div>
        <h1>Your external APIs,<br />mapped to the line.</h1>
        <p className="lede">
          A read-only inventory of every provider call, the models in use, and the lifecycle
          changes that need attention.
        </p>
      </header>

      {repositories.length > 0 && (
        <section className="repository-picker" aria-label="GitHub repositories">
          <div><span className="eyebrow">Connected installation</span><h2>Index a repository</h2></div>
          <div className="repository-actions">
            {repositories.map((repository) => (
              <button
                key={repository.id}
                disabled={indexing !== null}
                onClick={() => void indexRepository(repository)}
              >
                {indexing === repository.fullName ? "Indexing…" : repository.fullName}
              </button>
            ))}
          </div>
        </section>
      )}
      {connectionError && connectionError !== "GitHub is not connected" && (
        <p className="connection-error" role="alert">{connectionError}</p>
      )}

      <section className="metrics" aria-label="Inventory summary">
        <article><strong>{inventory.repositories.length}</strong><span>Repositories</span></article>
        <article><strong>{inventory.providers.length}</strong><span>Providers</span></article>
        <article><strong>{inventory.call_site_count}</strong><span>Call sites</span></article>
        <article className="attention"><strong>{inventory.attention_count}</strong><span>Need attention</span></article>
      </section>

      <section className="inventory">
        <div className="section-heading">
          <div><span className="eyebrow">Live inventory</span><h2>Dependencies</h2></div>
          <span className="repo-list">{inventory.repositories.join(" · ") || "No repository indexed"}</span>
        </div>
        {inventory.dependencies.length === 0 ? (
          <div className="empty">
            <h3>Connect the first inventory</h3>
            <p>Connect GitHub above, then choose a repository for ephemeral indexing.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Provider / surface</th><th>Model</th><th>Status</th><th>Locations</th></tr></thead>
              <tbody>
                {inventory.dependencies.map((dependency) => (
                  <tr key={`${dependency.surface.provider}:${dependency.surface.resource}:${dependency.surface.value}:${dependency.value_binding}`}>
                    <td><b>{dependency.surface.provider}</b><small>{dependency.surface.resource}.{dependency.surface.operation}</small></td>
                    <td><code>{dependency.surface.value ?? dependency.value_binding}</code>{dependency.replacement && <small>→ {dependency.replacement}</small>}</td>
                    <td><Status value={dependency.status} />{dependency.effective_at && <small>{dependency.effective_at}</small>}</td>
                    <td><b>{dependency.locations.length}</b><small>{dependency.locations[0].file_path}:{dependency.locations[0].line}</small></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="inventory" aria-label="Change feed">
        <div className="section-heading">
          <div><span className="eyebrow">Change feed</span><h2>Changes</h2></div>
          <span className="repo-list">{affected.length} of {impacts.impacts.length} events affect this inventory</span>
        </div>
        {affected.length === 0 ? (
          <div className="empty">
            <h3>Nothing affected</h3>
            <p>No tracked change event matches an indexed call site.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Change</th><th>Effective</th><th>Blast radius</th><th>First match</th></tr></thead>
              <tbody>
                {affected.map((impact) => (
                  <tr key={`${impact.event.surface.provider}:${impact.event.surface.value}:${impact.event.change_type}`}>
                    <td><b>{impact.event.surface.provider}</b><small>{impact.event.summary ?? impact.event.change_type}</small></td>
                    <td><span className={`status status-${impact.event.severity}`}>{impact.event.severity}</span>{impact.event.effective_at && <small>{impact.event.effective_at}</small>}</td>
                    <td>{impact.blast_radius}</td>
                    <td><code>{impact.matches[0].match_kind}</code><small>{impact.matches[0].file_path}:{impact.matches[0].line_start}</small></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </main>
  );
}
