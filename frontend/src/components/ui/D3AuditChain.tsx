"use client";

import React, { useEffect, useRef } from "react";
import * as d3 from "d3";
import type { AuditEntry } from "@/lib/api/types";

interface D3AuditChainProps {
  chain: AuditEntry[];
}

export default function D3AuditChain({ chain }: D3AuditChainProps) {
  const svgRef = useRef<SVGSVGElement>(null);

  useEffect(() => {
    if (!svgRef.current || chain.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove();

    const nodeWidth = 260;
    const nodeHeight = 120;
    const horizontalSpacing = 80;
    
    const margin = { top: 40, right: 40, bottom: 40, left: 40 };
    const width = chain.length * (nodeWidth + horizontalSpacing) + margin.left + margin.right;
    const height = nodeHeight + margin.top + margin.bottom;

    svg.attr("width", width).attr("height", height);

    const g = svg.append("g").attr("transform", `translate(${margin.left},${margin.top})`);

    // Define colors using CSS variables from globals.css
    const getCssVar = (name: string) => {
      if (typeof window !== "undefined") {
        return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
      }
      return "#000"; // fallback
    };

    const colorBgSecondary = getCssVar("--color-bg-secondary") || "#0f1011";
    const colorBorder = getCssVar("--color-border") || "#262626";
    const colorBorderHover = getCssVar("--color-border-hover") || "#404040";
    const colorTextPrimary = getCssVar("--color-text-primary") || "#ededed";
    const colorTextSecondary = getCssVar("--color-text-secondary") || "#a3a3a3";
    const colorTextTertiary = getCssVar("--color-text-tertiary") || "#737373";
    const colorTextQuaternary = getCssVar("--color-text-quaternary") || "#525252";

    // Draw connecting lines (the blockchain links)
    g.selectAll(".link")
      .data(chain.slice(1))
      .enter()
      .append("path")
      .attr("class", "link")
      .attr("d", (d, i) => {
        const x0 = i * (nodeWidth + horizontalSpacing) + nodeWidth;
        const y0 = nodeHeight / 2;
        const x1 = (i + 1) * (nodeWidth + horizontalSpacing);
        const y1 = nodeHeight / 2;
        return `M${x0},${y0} L${x1},${y1}`;
      })
      .attr("fill", "none")
      .attr("stroke", colorBorderHover)
      .attr("stroke-width", 1)
      .attr("stroke-dasharray", "4,4");

    // Draw nodes
    const nodes = g.selectAll(".node")
      .data(chain)
      .enter()
      .append("g")
      .attr("class", "node")
      .attr("transform", (d, i) => `translate(${i * (nodeWidth + horizontalSpacing)}, 0)`);

    // Node Background
    nodes.append("rect")
      .attr("width", nodeWidth)
      .attr("height", nodeHeight)
      .attr("fill", colorBgSecondary)
      .attr("stroke", colorBorder)
      .attr("stroke-width", 1)
      .attr("rx", 6) // match var(--border-radius-md)
      .attr("ry", 6);

    // Block Index Label
    nodes.append("text")
      .attr("x", 16)
      .attr("y", 28)
      .attr("fill", colorTextTertiary)
      .style("font-family", "var(--font-mono)")
      .style("font-size", "12px")
      .style("font-weight", "500")
      .style("letter-spacing", "0.05em")
      .text((d) => `BLOCK ${d.index.toString().padStart(4, '0')}`);

    // Event Type
    nodes.append("text")
      .attr("x", 16)
      .attr("y", 52)
      .attr("fill", colorTextPrimary)
      .style("font-family", "var(--font-sans)")
      .style("font-size", "14px")
      .style("font-weight", "600")
      .text((d) => d.event_type.replace(/_/g, " "));

    // Payload Hash (Truncated)
    nodes.append("text")
      .attr("x", 16)
      .attr("y", 78)
      .attr("fill", colorTextSecondary)
      .style("font-family", "var(--font-mono)")
      .style("font-size", "11px")
      .text((d) => `Hash: ${d.payload_hash.substring(0, 24)}...`);

    // Previous Hash
    nodes.append("text")
      .attr("x", 16)
      .attr("y", 94)
      .attr("fill", colorTextTertiary)
      .style("font-family", "var(--font-mono)")
      .style("font-size", "10px")
      .text((d) => d.prev_hash ? `Prev: ${d.prev_hash.substring(0, 24)}...` : `Prev: null (genesis)`);

    // Time
    nodes.append("text")
      .attr("x", 16)
      .attr("y", 110)
      .attr("fill", colorTextQuaternary)
      .style("font-family", "var(--font-mono)")
      .style("font-size", "10px")
      .text((d) => {
        const date = new Date(d.created_at);
        return isNaN(date.getTime()) ? d.created_at : date.toISOString().replace("T", " ").substring(0, 19) + " UTC";
      });

    // Hover interactions
    nodes.on("mouseenter", function(event, d) {
      d3.select(this).select("rect")
        .attr("stroke", colorBorderHover);
      
      d3.select(this).style("cursor", "pointer");
    }).on("mouseleave", function(event, d) {
      d3.select(this).select("rect")
        .attr("stroke", colorBorder);
    });

  }, [chain]);

  return (
    <div className="w-full overflow-x-auto custom-scrollbar" style={{ backgroundColor: "var(--color-bg-primary)" }}>
      <svg ref={svgRef} className="block min-w-max"></svg>
    </div>
  );
}
