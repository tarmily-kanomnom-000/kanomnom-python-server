"use client";

import { useEffect, useMemo, useState } from "react";

import { ListControls, type SortRule } from "@/components/grocy/list-controls";
import type { GrocyInstanceSummary } from "@/lib/grocy/types";

import { buildInstanceLabel, buildSearchTarget } from "./helpers";

type InstanceSelectorProps = {
  instances: GrocyInstanceSummary[];
  selectedInstanceId: string | null;
  onInstanceChange: (instanceId: string | null) => void;
};

type InstanceSortField = "name" | "locationTypes" | "locationCount";

type InstanceSortState = SortRule<InstanceSortField>[];

const INSTANCE_SORT_OPTIONS: Array<{
  label: string;
  value: InstanceSortField;
}> = [
  { label: "Name", value: "name" },
  { label: "Location types", value: "locationTypes" },
  { label: "Location count", value: "locationCount" },
];

export function InstanceSelector({
  instances,
  selectedInstanceId,
  onInstanceChange,
}: InstanceSelectorProps) {
  const [searchValue, setSearchValue] = useState("");
  const [isDropdownOpen, setDropdownOpen] = useState(false);
  const [isSelectorOpen, setSelectorOpen] = useState(false);
  const [isInstanceFilterVisible, setInstanceFilterVisible] = useState(false);
  const [selectedTypes, setSelectedTypes] = useState<string[]>([]);
  const [instanceSortState, setInstanceSortState] = useState<InstanceSortState>(
    [{ field: "name", direction: "asc" }],
  );

  const selectedInstance = useMemo(
    () =>
      instances.find(
        (instance) => instance.instance_index === selectedInstanceId,
      ) ?? null,
    [instances, selectedInstanceId],
  );

  const availableTypes = useMemo(() => {
    const unique = new Set<string>();
    instances.forEach((instance) => {
      instance.location_types.forEach((type) => {
        unique.add(type);
      });
    });
    return Array.from(unique).sort((a, b) => a.localeCompare(b));
  }, [instances]);

  useEffect(() => {
    if (selectedInstance && !isSelectorOpen) {
      setSearchValue(buildInstanceLabel(selectedInstance));
    }
  }, [selectedInstance, isSelectorOpen]);

  const filteredInstances = useMemo(() => {
    const normalizedQuery = searchValue.trim().toLowerCase();
    const filtered = instances.filter((instance) => {
      const matchesQuery =
        normalizedQuery.length === 0 ||
        buildSearchTarget(instance).includes(normalizedQuery);
      const matchesTypes =
        selectedTypes.length === 0 ||
        selectedTypes.every((type) => instance.location_types.includes(type));
      return matchesQuery && matchesTypes;
    });
    filtered.sort((a, b) => compareInstances(a, b, instanceSortState));
    return filtered;
  }, [instances, searchValue, selectedTypes, instanceSortState]);

  if (instances.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-neutral-300 bg-white p-8 text-center text-neutral-600">
        No Grocy instances are registered with the API yet.
      </div>
    );
  }

  const handleSelect = (instance: GrocyInstanceSummary) => {
    onInstanceChange(instance.instance_index);
    setSearchValue(buildInstanceLabel(instance));
    setDropdownOpen(false);
    setSelectorOpen(false);
    setInstanceFilterVisible(false);
  };

  const toggleType = (type: string) => {
    setSelectedTypes((current) =>
      current.includes(type)
        ? current.filter((value) => value !== type)
        : [...current, type],
    );
  };

  const handleInstanceSearchChange = (value: string) => {
    if (!isSelectorOpen) {
      return;
    }
    setSearchValue(value);
    setDropdownOpen(value.trim().length > 0);
  };

  const shouldShowSuggestions =
    isSelectorOpen &&
    isDropdownOpen &&
    (searchValue.trim().length > 0 || isInstanceFilterVisible);
  const collapsedLabel = selectedInstance
    ? buildInstanceLabel(selectedInstance)
    : "Select a Grocy instance";

  return (
    <div className="rounded-3xl border border-neutral-200 bg-white p-5 shadow-sm">
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-xs uppercase tracking-wide text-neutral-500">
            Instance selector
          </p>
          <button
            type="button"
            onClick={() => {
              setSelectorOpen((open) => {
                if (open) {
                  setDropdownOpen(false);
                  setInstanceFilterVisible(false);
                }
                return !open;
              });
            }}
            className="text-neutral-500 transition-transform hover:text-neutral-800"
            aria-label="Toggle selector"
          >
            <span
              className={`inline-block transform transition-transform ${
                isSelectorOpen ? "-rotate-180" : ""
              }`}
            >
              ▼
            </span>
          </button>
        </div>

        <ListControls
          searchLabel="Search Grocy instances"
          searchPlaceholder="Start typing a name or address…"
          searchValue={isSelectorOpen ? searchValue : collapsedLabel}
          onSearchChange={handleInstanceSearchChange}
          searchInputClassName={isSelectorOpen ? "" : "cursor-pointer"}
          searchInputProps={{
            readOnly: !isSelectorOpen,
            onFocus: () => {
              if (!isSelectorOpen) {
                setSelectorOpen(true);
                setSearchValue("");
                setDropdownOpen(false);
              }
            },
            onBlur: () => {
              window.setTimeout(() => setDropdownOpen(false), 100);
            },
          }}
          searchResults={
            shouldShowSuggestions ? (
              <div
                className="absolute z-10 mt-2 max-h-64 w-full overflow-y-auto rounded-2xl border border-neutral-100 bg-white shadow-lg"
                onMouseDown={(event) => event.preventDefault()}
              >
                {filteredInstances.length > 0 ? (
                  filteredInstances.map((instance) => (
                    <button
                      type="button"
                      key={instance.instance_index}
                      onClick={() => handleSelect(instance)}
                      className={`flex w-full flex-col items-start gap-1 px-4 py-3 text-left text-sm transition ${
                        instance.instance_index === selectedInstanceId
                          ? "bg-neutral-900 text-white"
                          : "hover:bg-neutral-100"
                      }`}
                    >
                      <span className="font-medium">
                        {buildInstanceLabel(instance)}
                      </span>
                      <span
                        className={`text-xs ${
                          instance.instance_index === selectedInstanceId
                            ? "text-neutral-200"
                            : "text-neutral-500"
                        }`}
                      >
                        {instance.location_types.join(", ") || "Uncategorized"}
                        {" • "}
                        {instance.locations.length} location
                        {instance.locations.length === 1 ? "" : "s"}
                      </span>
                      <span
                        className={`text-[11px] ${
                          instance.instance_index === selectedInstanceId
                            ? "text-neutral-100"
                            : "text-neutral-400"
                        }`}
                      >
                        {formatInstanceLocations(instance)}
                      </span>
                    </button>
                  ))
                ) : (
                  <p className="px-4 py-3 text-sm text-neutral-500">
                    No instances match “{searchValue}”.
                  </p>
                )}
              </div>
            ) : null
          }
          filters={
            availableTypes.length > 0
              ? {
                  fields: [
                    {
                      id: "location_types",
                      label: "Location types",
                      type: "text",
                      values: availableTypes,
                      selectedValues: selectedTypes,
                      onToggle: toggleType,
                      onClear: () => setSelectedTypes([]),
                    },
                  ],
                  buttonLabel: "Filters +",
                  disabled: !isSelectorOpen,
                  onVisibilityChange: setInstanceFilterVisible,
                }
              : undefined
          }
          sortOptions={INSTANCE_SORT_OPTIONS}
          sortState={instanceSortState}
          maxSortLevels={3}
          onSortChange={setInstanceSortState}
        />

        {isSelectorOpen ? (
          <div className="space-y-4 border-t border-neutral-100 pt-4">
            <p className="text-sm font-medium text-neutral-700">
              Instance details
            </p>

            {selectedInstance ? (
              <InstanceDetails instance={selectedInstance} />
            ) : (
              <div className="rounded-2xl border border-dashed border-neutral-300 bg-neutral-50 px-4 py-6 text-sm text-neutral-600">
                Start typing to choose a Grocy instance.
              </div>
            )}
          </div>
        ) : null}
      </div>
    </div>
  );
}

function InstanceDetails({ instance }: { instance: GrocyInstanceSummary }) {
  return (
    <div className="rounded-2xl border border-neutral-100 bg-neutral-50 p-6 text-sm text-neutral-700">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-neutral-500">
            Instance
          </p>
          <p className="mt-1 text-lg font-semibold text-neutral-900">
            {buildInstanceLabel(instance)}
          </p>
          <p className="text-xs text-neutral-500">
            Identifier {instance.instance_index}
          </p>
        </div>
        <div className="text-sm text-neutral-600">
          <p className="font-medium">
            {instance.location_types.length > 0
              ? instance.location_types.join(", ")
              : "Uncategorized"}
          </p>
          <p className="text-xs text-neutral-500">
            {instance.locations.length} location
            {instance.locations.length === 1 ? "" : "s"}
          </p>
        </div>
      </div>
      {instance.address ? (
        <div className="mt-4 text-sm text-neutral-700">
          <p className="text-xs uppercase tracking-wide text-neutral-500">
            Address
          </p>
          <address className="mt-1 not-italic leading-relaxed">
            {[instance.address.line1, instance.address.line2]
              .filter(Boolean)
              .join("\n")}
            <br />
            {instance.address.city}, {instance.address.state}{" "}
            {instance.address.postal_code}
            <br />
            {instance.address.country}
          </address>
        </div>
      ) : null}
      {instance.locations.length > 0 ? (
        <div className="mt-4 text-sm text-neutral-700">
          <p className="text-xs uppercase tracking-wide text-neutral-500">
            Locations
          </p>
          <ul className="mt-2 space-y-1">
            {instance.locations.map((location) => (
              <li key={location.id} className="text-neutral-600">
                <span className="font-medium text-neutral-900">
                  {location.name}
                </span>
                {location.description ? (
                  <span className="text-neutral-500">
                    {" "}
                    — {location.description}
                  </span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function formatInstanceLocations(instance: GrocyInstanceSummary): string {
  if (instance.locations.length === 0) {
    return "No locations configured yet";
  }
  const names = instance.locations
    .map((location) => location.name)
    .filter(Boolean);
  if (names.length === 0) {
    return "Locations have no names";
  }
  if (names.length <= 3) {
    return names.join(", ");
  }
  const displayed = names.slice(0, 3).join(", ");
  return `${displayed}, +${names.length - 3} more`;
}

function compareInstances(
  a: GrocyInstanceSummary,
  b: GrocyInstanceSummary,
  sortState: InstanceSortState,
): number {
  if (sortState.length === 0) {
    return buildInstanceLabel(a).localeCompare(buildInstanceLabel(b));
  }

  for (const rule of sortState) {
    const directionMultiplier = rule.direction === "asc" ? 1 : -1;
    if (rule.field === "locationTypes") {
      const difference = a.location_types.length - b.location_types.length;
      if (difference !== 0) {
        return difference * directionMultiplier;
      }
      continue;
    }
    if (rule.field === "locationCount") {
      const difference = a.locations.length - b.locations.length;
      if (difference !== 0) {
        return difference * directionMultiplier;
      }
      continue;
    }
    const nameComparison =
      buildInstanceLabel(a).localeCompare(buildInstanceLabel(b)) *
      directionMultiplier;
    if (nameComparison !== 0) {
      return nameComparison;
    }
  }

  return buildInstanceLabel(a).localeCompare(buildInstanceLabel(b));
}
