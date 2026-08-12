import { loadInventoryFromEnvironment, type LifecycleStatus } from "@/inventory/inventory";

export const dynamic = "force-dynamic";

function Status({ value }: { value: LifecycleStatus }) {
  return <span className={`status status-${value}`}>{value}</span>;
}

export default async function InventoryPage() {
  const inventory = await loadInventoryFromEnvironment();
  return (
    <main>
      <header>
        <div className="wordmark"><span>A</span> Avert</div>
        <div className="eyebrow">API dependency intelligence</div>
        <h1>Your external APIs,<br />mapped to the line.</h1>
        <p className="lede">
          A read-only inventory of every provider call, the models in use, and the lifecycle
          changes that need attention.
        </p>
      </header>

      <section className="metrics" aria-label="Inventory summary">
        <article><strong>{inventory.repositories.length}</strong><span>Repositories</span></article>
        <article><strong>{inventory.providers.length}</strong><span>Providers</span></article>
        <article><strong>{inventory.callSiteCount}</strong><span>Call sites</span></article>
        <article className="attention"><strong>{inventory.attentionCount}</strong><span>Need attention</span></article>
      </section>

      <section className="inventory">
        <div className="section-heading">
          <div><span className="eyebrow">Live inventory</span><h2>Dependencies</h2></div>
          <span className="repo-list">{inventory.repositories.join(" · ") || "No repository indexed"}</span>
        </div>
        {inventory.dependencies.length === 0 ? (
          <div className="empty">
            <h3>Connect the first inventory</h3>
            <p>Run the engine index command and set <code>AVERT_INVENTORY_PATH</code> to its JSONL output.</p>
          </div>
        ) : (
          <div className="table-wrap">
            <table>
              <thead><tr><th>Provider / surface</th><th>Model</th><th>Status</th><th>Locations</th></tr></thead>
              <tbody>
                {inventory.dependencies.map((dependency) => (
                  <tr key={`${dependency.provider}:${dependency.resource}:${dependency.model}:${dependency.valueBinding}`}>
                    <td><b>{dependency.provider}</b><small>{dependency.resource}.{dependency.operation}</small></td>
                    <td><code>{dependency.model ?? dependency.valueBinding}</code>{dependency.replacement && <small>→ {dependency.replacement}</small>}</td>
                    <td><Status value={dependency.status} />{dependency.effectiveAt && <small>{dependency.effectiveAt}</small>}</td>
                    <td><b>{dependency.locations.length}</b><small>{dependency.locations[0].filePath}:{dependency.locations[0].line}</small></td>
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
