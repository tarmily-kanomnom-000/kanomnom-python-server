"use client";

import { Fragment } from "react";
import { normalizeDescription } from "./product-metrics";

type DescriptionWithLinksProps = {
  description: string;
  className?: string;
};

const URL_REGEX = /(https?:\/\/[^\s]+)/gi;
const TRAILING_PUNCTUATION = /[),.;:?]+$/;

export function DescriptionWithLinks({
  description,
  className,
}: DescriptionWithLinksProps) {
  const normalized = normalizeDescription(description);
  const segments = splitWithUrls(normalized);
  if (segments.length === 0) {
    return null;
  }
  return (
    <p className={className}>
      {segments.map((segment, index) => {
        if (segment.kind === "link") {
          return (
            <a
              key={`${segment.value}-${index}`}
              href={segment.value}
              target="_blank"
              rel="noreferrer"
              className="underline underline-offset-2 transition hover:text-neutral-900"
            >
              {segment.label}
            </a>
          );
        }
        return (
          <Fragment key={`${segment.value}-${index}`}>{segment.value}</Fragment>
        );
      })}
    </p>
  );
}

type DescriptionSegment =
  | { kind: "text"; value: string }
  | { kind: "link"; value: string; label: string };

function splitWithUrls(text: string): DescriptionSegment[] {
  if (!text.trim()) {
    return [];
  }
  const segments: DescriptionSegment[] = [];
  let lastIndex = 0;
  for (const match of text.matchAll(URL_REGEX)) {
    const matchIndex = match.index ?? 0;
    const urlRaw = match[0];
    if (matchIndex > lastIndex) {
      segments.push({
        kind: "text",
        value: text.slice(lastIndex, matchIndex),
      });
    }
    const { url, trailing } = splitTrailingPunctuation(urlRaw);
    segments.push({
      kind: "link",
      value: url,
      label: decodeUrlForDisplay(url),
    });
    if (trailing) {
      segments.push({ kind: "text", value: trailing });
    }
    lastIndex = matchIndex + urlRaw.length;
  }
  if (lastIndex < text.length) {
    segments.push({ kind: "text", value: text.slice(lastIndex) });
  }
  return segments;
}

function splitTrailingPunctuation(value: string): {
  url: string;
  trailing: string;
} {
  const match = value.match(TRAILING_PUNCTUATION);
  if (!match) {
    return { url: value, trailing: "" };
  }
  const trailing = match[0];
  return { url: value.slice(0, -trailing.length), trailing };
}

function decodeUrlForDisplay(value: string): string {
  try {
    return decodeURI(value);
  } catch {
    return value;
  }
}
