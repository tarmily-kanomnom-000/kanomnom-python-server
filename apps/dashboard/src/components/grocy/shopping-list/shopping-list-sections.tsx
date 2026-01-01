import type { ShoppingListSection } from "@/hooks/useShoppingListController";
import type { ItemUpdate } from "@/lib/grocy/shopping-list-types";
import { ShoppingListItemCard } from "./shopping-list-item-card";

type Props = {
  sections: ShoppingListSection[];
  collapsedSections: Record<string, boolean>;
  onToggleSection: (locationKey: string) => void;
  onCheckSection: (locationKey: string) => void;
  onUncheckSection: (locationKey: string) => void;
  onUpdateItem: (itemId: string, updates: ItemUpdate) => Promise<void>;
  onDeleteItem: (itemId: string) => Promise<void>;
};

export function ShoppingListSections({
  sections,
  collapsedSections,
  onToggleSection,
  onCheckSection,
  onUncheckSection,
  onUpdateItem,
  onDeleteItem,
}: Props) {
  return (
    <div className="space-y-6">
      {sections.map((section) => {
        const isCollapsed = collapsedSections[section.locationKey] ?? false;

        return (
          <div
            key={section.locationKey}
            className="rounded-lg border bg-white p-4"
          >
            <div className="mb-3 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={section.allChecked}
                  ref={(el) => {
                    if (el) {
                      el.indeterminate = section.someChecked;
                    }
                  }}
                  onChange={(e) => {
                    if (e.target.checked) {
                      onCheckSection(section.locationKey);
                    } else {
                      onUncheckSection(section.locationKey);
                    }
                  }}
                  className="h-6 w-6 shrink-0 cursor-pointer rounded border-gray-300 text-green-600 focus:ring-2 focus:ring-green-500 focus:ring-offset-0"
                />
                <button
                  onClick={() => onToggleSection(section.locationKey)}
                  className="flex items-center gap-2 text-left transition-colors hover:text-gray-600"
                >
                  <h2 className="text-lg font-semibold text-gray-800">
                    {section.locationName}
                    <span className="ml-2 text-sm font-normal text-gray-500">
                      ({section.purchasedCount}/{section.totalCount})
                    </span>
                  </h2>
                </button>
              </div>
              <button
                onClick={() => onToggleSection(section.locationKey)}
                className="transition-colors hover:text-gray-600"
              >
                <svg
                  className={`h-5 w-5 transform transition-transform ${
                    isCollapsed ? "-rotate-90" : ""
                  }`}
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </button>
            </div>

            {!isCollapsed && (
              <div className="space-y-2">
                {section.items.map((item) => (
                  <ShoppingListItemCard
                    key={item.id}
                    item={item}
                    onUpdate={onUpdateItem}
                    onDelete={onDeleteItem}
                  />
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
