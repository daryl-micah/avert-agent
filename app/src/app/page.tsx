import { InventoryDashboard } from "@/app/inventory-dashboard";
import { loadInventoryFromEnvironment } from "@/inventory/inventory";

export const dynamic = "force-dynamic";

export default async function InventoryPage() {
  const inventory = await loadInventoryFromEnvironment();
  return <InventoryDashboard initialInventory={inventory} />;
}
