import { InventoryDashboard } from "@/app/inventory-dashboard";
import { connectedInstallationId } from "@/github/session";
import { impactsForInstallation, inventoryForInstallation } from "@/inventory/inventory";

export const dynamic = "force-dynamic";

export default async function InventoryPage() {
  const installationId = await connectedInstallationId();
  const [inventory, impacts] = await Promise.all([
    inventoryForInstallation(installationId),
    impactsForInstallation(installationId),
  ]);
  return <InventoryDashboard initialInventory={inventory} initialImpacts={impacts} />;
}
