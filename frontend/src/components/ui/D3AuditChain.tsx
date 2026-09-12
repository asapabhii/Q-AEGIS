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

    // Define colors - Quantum Futurism
    const colorCyan = "#00FFFF";
    const colorMagenta = "#FF00FF";
    const colorAcid = "#8CFF00";
    const colorBg = "#000000";
    const colorBorder = "#333333";

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
      .attr("stroke", colorCyan)
      .attr("stroke-width", 2)
      .attr("stroke-dasharray", "4,4")
      .style("filter", `drop-shadow(0 0 4px ${colorCyan})`);

    // Draw nodes
    const nodes = g.selectAll(".node")
      .data(chain)
      .enter()
      .append("g")
      .attr("class", "node")
      .attr("transform", (d, i) => `translate(${i * (nodeWidth + horizontalSpacing)}, 0)`);

    // Node Background (Sharp corners, no rounding)
    nodes.append("rect")
      .attr("width", nodeWidth)
      .attr("height", nodeHeight)
      .attr("fill", colorBg)
      .attr("stroke", colorBorder)
      .attr("stroke-width", 1)
      .style("filter", `drop-shadow(0 0 8px ${colorCyan}33)`);

    // Block Index Label
    nodes.append("text")
      .attr("x", 12)
      .attr("y", 24)
      .attr("fill", colorAcid)
      .style("font-family", "monospace")
      .style("font-size", "12px")
      .style("font-weight", "bold")
      .style("letter-spacing", "0.1em")
      .text((d) => `BLOCK ${d.index.toString().padStart(4, '0')}`);

    // Event Type
    nodes.append("text")
      .attr("x", 12)
      .attr("y", 46)
      .attr("fill", "#FFFFFF")
      .style("font-family", "sans-serif")
      .style("font-size", "14px")
      .style("font-weight", "600")
      .text((d) => d.event_type.replace(/_/g, " ").toUpperCase());

    // Payload Hash (Truncated)
    nodes.append("text")
      .attr("x", 12)
      .attr("y", 76)
      .attr("fill", colorMagenta)
      .style("font-family", "monospace")
      .style("font-size", "11px")
      .text((d) => `HASH: ${d.payload_hash.substring(0, 24)}...`);

    // Previous Hash
    nodes.append("text")
      .attr("x", 12)
      .attr("y", 92)
      .attr("fill", "#888888")
      .style("font-family", "monospace")
      .style("font-size", "10px")
      .text((d) => d.prev_hash ? `PREV: ${d.prev_hash.substring(0, 24)}...` : `PREV: NULL (GENESIS)`);

    // Time
    nodes.append("text")
      .attr("x", 12)
      .attr("y", 108)
      .attr("fill", "#555555")
      .style("font-family", "monospace")
      .style("font-size", "10px")
      .text((d) => {
        const date = new Date(d.created_at);
        return isNaN(date.getTime()) ? d.created_at : date.toISOString().replace("T", " ").substring(0, 19) + " UTC";
      });

    // Hover interactions
    nodes.on("mouseenter", function(event, d) {
      d3.select(this).select("rect")
        .attr("stroke", colorCyan)
        .style("filter", `drop-shadow(0 0 12px ${colorCyan}66)`);
      
      d3.select(this).style("cursor", "crosshair");
    }).on("mouseleave", function(event, d) {
      d3.select(this).select("rect")
        .attr("stroke", colorBorder)
        .style("filter", `drop-shadow(0 0 8px ${colorCyan}33)`);
    });

  }, [chain]);

  return (
    <div className="w-full overflow-x-auto border border-[#333] bg-black scrollbar-thin scrollbar-thumb-cyan-500 scrollbar-track-black" style={{ borderRadius: "0px" }}>
      <svg ref={svgRef} className="block min-w-max"></svg>
    </div>
  );
}
