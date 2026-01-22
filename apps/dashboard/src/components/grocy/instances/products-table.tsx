"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

import type { GrocyProductInventoryEntry } from "@/lib/grocy/types";
import { DescriptionWithLinks } from "./description-with-links";
import {
  formatLastUpdated,
  formatQuantityWithUnit,
  resolveProductGroup,
} from "./helpers";
import { ACTION_MENU_OPTIONS, type ProductActionType } from "./product-actions";
import {
  formatMinimumStock,
  ProductStockStatus,
  resolveDaysSinceUpdate,
  resolveProductStockStatus,
} from "./product-metrics";

type ProductsTableProps = {
  products: GrocyProductInventoryEntry[];
  onSelectProduct: (product: GrocyProductInventoryEntry) => void;
  onSelectAction: (
    product: GrocyProductInventoryEntry,
    action: ProductActionType,
  ) => void;
  productInteractionMode: "details" | "purchase" | "inventory";
  onQuickSetZero: (product: GrocyProductInventoryEntry) => void;
  quickActionPendingIds: Set<number>;
};

export function ProductsTable({
  products,
  onSelectProduct,
  onSelectAction,
  productInteractionMode,
  onQuickSetZero,
  quickActionPendingIds,
}: ProductsTableProps) {
  const showQuickSetZero = productInteractionMode === "inventory";
  return (
    <div className="overflow-visible rounded-2xl border border-neutral-100 bg-white">
      <table className="min-w-full divide-y divide-neutral-200 text-left text-sm text-neutral-800">
        <thead className="bg-neutral-50 text-xs uppercase tracking-wide text-neutral-500">
          <tr>
            <th className="px-4 py-3 font-medium">Product</th>
            <th className="px-4 py-3 font-medium">Product group</th>
            <th className="px-4 py-3 font-medium">Stock status</th>
            <th className="px-4 py-3 font-medium">Amount in stock</th>
            <th className="px-4 py-3 font-medium">Days since update</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-neutral-100">
          {products.map((product) => {
            const rowKey = `${product.id}-${product.last_stock_updated_at.getTime?.() ?? product.last_stock_updated_at}`;
            const stockStatus = resolveProductStockStatus(product);
            const isQuickActionPending = quickActionPendingIds.has(product.id);
            const rowToneClass =
              stockStatus?.tone === "critical"
                ? "bg-red-100"
                : stockStatus?.tone === "warning"
                  ? "bg-orange-100"
                  : stockStatus?.tone === "caution"
                    ? "bg-yellow-100"
                    : stockStatus?.tone === "healthy"
                      ? "bg-green-100"
                      : "";
            const daysSince = resolveDaysSinceUpdate(product);
            return (
              <tr key={rowKey} className={`group align-top ${rowToneClass}`}>
                <td className="relative px-4 py-3">
                  <button
                    type="button"
                    onClick={() => onSelectProduct(product)}
                    className="w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-900/30"
                  >
                    <p className="font-medium text-neutral-900">
                      {product.name}
                    </p>
                  </button>
                  <ProductQuickPreview product={product} />
                </td>
                <td className="px-4 py-3 text-sm text-neutral-600">
                  <button
                    type="button"
                    onClick={() => onSelectProduct(product)}
                    className="w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-900/30"
                  >
                    {resolveProductGroup(product)}
                  </button>
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() => onSelectProduct(product)}
                    className="w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-900/30"
                  >
                    <StockStatusBadge status={stockStatus} />
                  </button>
                </td>
                <td className="px-4 py-3">
                  <button
                    type="button"
                    onClick={() => onSelectProduct(product)}
                    className="w-full text-left font-semibold text-neutral-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-900/30"
                  >
                    {formatQuantityWithUnit(product)}
                  </button>
                </td>
                <td className="relative px-4 py-3 text-sm text-neutral-600 pr-10">
                  <button
                    type="button"
                    onClick={() => onSelectProduct(product)}
                    className="w-full text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-900/30"
                  >
                    {daysSince} day{daysSince === 1 ? "" : "s"}
                  </button>
                  <div className="absolute right-2 top-1/2 -translate-y-1/2">
                    <div className="flex items-center gap-2">
                      {showQuickSetZero ? (
                        <button
                          type="button"
                          onClick={(event) => {
                            event.stopPropagation();
                            onQuickSetZero(product);
                          }}
                          disabled={isQuickActionPending}
                          className="inline-flex items-center rounded-full border border-red-300 bg-red-100 px-2.5 py-1 text-[11px] font-semibold text-red-700 transition hover:border-red-400 hover:bg-red-200 disabled:cursor-not-allowed disabled:border-red-200 disabled:bg-red-50 disabled:text-red-400"
                        >
                          {isQuickActionPending ? "Setting…" : "Set to 0"}
                        </button>
                      ) : null}
                      <ProductRowActions
                        product={product}
                        onActionSelect={(action) =>
                          onSelectAction(product, action)
                        }
                      />
                    </div>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ProductRowActions({
  product,
  onActionSelect,
}: {
  product: GrocyProductInventoryEntry;
  onActionSelect: (action: ProductActionType) => void;
}) {
  const [isMenuOpen, setMenuOpen] = useState(false);
  const [menuPosition, setMenuPosition] = useState<{
    top: number;
    left: number;
  } | null>(null);
  const containerRef = useRef<HTMLDivElement | null>(null);

  const closeMenu = useCallback(() => {
    setMenuOpen(false);
  }, []);

  const updateMenuPosition = useCallback(() => {
    if (!containerRef.current) {
      setMenuPosition(null);
      return;
    }
    const rect = containerRef.current.getBoundingClientRect();
    setMenuPosition({
      top: rect.top + rect.height / 2,
      left: rect.left,
    });
  }, []);

  const handleToggle = (event: React.MouseEvent) => {
    event.stopPropagation();
    if (isMenuOpen) {
      closeMenu();
      return;
    }
    updateMenuPosition();
    setMenuOpen(true);
  };

  useEffect(() => {
    if (!isMenuOpen) {
      setMenuPosition(null);
      return;
    }
    updateMenuPosition();
    const handleViewportChange = () => {
      if (!containerRef.current) {
        closeMenu();
        return;
      }
      updateMenuPosition();
    };
    window.addEventListener("resize", handleViewportChange);
    window.addEventListener("scroll", handleViewportChange, true);
    return () => {
      window.removeEventListener("resize", handleViewportChange);
      window.removeEventListener("scroll", handleViewportChange, true);
    };
  }, [isMenuOpen, closeMenu, updateMenuPosition]);

  return (
    <div className="relative inline-block text-left" ref={containerRef}>
      <button
        type="button"
        onClick={handleToggle}
        className="inline-flex items-center justify-center rounded-full border border-neutral-200 bg-white p-1.5 text-neutral-500 shadow-sm transition hover:border-neutral-900 hover:text-neutral-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neutral-900/30"
        aria-label={`Open actions for ${product.name}`}
      >
        <VerticalDotsIcon />
      </button>
      {isMenuOpen && menuPosition
        ? createPortal(
            <>
              <div className="fixed inset-0 z-40" onClick={closeMenu} />
              <div
                className="fixed z-[70] w-52 rounded-2xl border border-neutral-200 bg-white p-2 text-sm shadow-2xl"
                onClick={(event) => event.stopPropagation()}
                style={{
                  top: menuPosition.top,
                  left: menuPosition.left,
                  transform: "translate(calc(-100% - 0.75rem), -50%)",
                }}
              >
                {ACTION_MENU_OPTIONS.map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={(event) => {
                      event.stopPropagation();
                      onActionSelect(option.value);
                      closeMenu();
                    }}
                    className="w-full rounded-xl px-3 py-2 text-left text-neutral-700 hover:bg-neutral-50"
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </>,
            document.body,
          )
        : null}
    </div>
  );
}

function ProductQuickPreview({
  product,
}: {
  product: GrocyProductInventoryEntry;
}) {
  return (
    <div className="pointer-events-none absolute left-1/4 top-1/2 z-20 hidden w-72 -translate-y-1/2 rounded-2xl border border-neutral-200 bg-white p-4 text-xs text-neutral-700 shadow-2xl opacity-0 transition duration-150 ease-out group-hover:opacity-100 group-hover:visible lg:block">
      <p className="text-[11px] uppercase tracking-wide text-neutral-400">
        Quick view
      </p>
      <p className="mt-1 text-sm font-semibold text-neutral-900">
        {product.name}
      </p>
      <p className="text-[11px] text-neutral-500">
        {resolveProductGroup(product)}
      </p>
      {product.description ? (
        <DescriptionWithLinks
          description={product.description}
          className="mt-2 line-clamp-2 whitespace-pre-line text-[11px] text-neutral-600"
        />
      ) : null}
      <dl className="mt-3 space-y-2">
        <div className="flex items-center justify-between">
          <dt className="text-neutral-500">Stock</dt>
          <dd className="font-medium text-neutral-900">
            {formatQuantityWithUnit(product)}
          </dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-neutral-500">Minimum</dt>
          <dd className="font-medium text-neutral-900">
            {formatMinimumStock(product)}
          </dd>
        </div>
        <div className="flex items-center justify-between">
          <dt className="text-neutral-500">Updated</dt>
          <dd className="font-medium text-neutral-900">
            {formatLastUpdated(product.last_stock_updated_at)}
          </dd>
        </div>
      </dl>
    </div>
  );
}

function StockStatusBadge({ status }: { status: ProductStockStatus }) {
  const toneClasses =
    status.tone === "critical"
      ? "border-red-400 bg-red-200 text-red-900"
      : status.tone === "warning"
        ? "border-orange-400 bg-orange-200 text-orange-900"
        : status.tone === "caution"
          ? "border-yellow-500 bg-yellow-200 text-yellow-900"
          : status.tone === "healthy"
            ? "border-emerald-500 bg-emerald-100 text-emerald-900"
            : "border-neutral-200 bg-neutral-100 text-neutral-600";
  return (
    <span
      className={`inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-semibold ${toneClasses}`}
    >
      {status.label}
    </span>
  );
}

function VerticalDotsIcon() {
  return (
    <span className="flex flex-col items-center justify-center gap-0.5">
      <span className="block h-1 w-1 rounded-full bg-current" />
      <span className="block h-1 w-1 rounded-full bg-current" />
      <span className="block h-1 w-1 rounded-full bg-current" />
    </span>
  );
}
