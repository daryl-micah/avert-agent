import { InventoryDashboard } from "@/app/inventory-dashboard";
import { connectedInstallationId } from "@/github/session";
import { inventoryForInstallation } from "@/inventory/inventory";

export const dynamic = "force-dynamic";

export default async function InventoryPage() {
  const inventory = await inventoryForInstallation(await connectedInstallationId());
  return <InventoryDashboard initialInventory={inventory} />;
}
