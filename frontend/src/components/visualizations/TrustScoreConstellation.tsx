"use client";

import { useEffect, useRef, useState } from "react";
import * as d3 from "d3";

export interface AgentScore {
  type: "security" | "compliance" | "contextual" | "quantum" | "sustainability";
  score: number;
  rationale: string;
}

interface TrustScoreConstellationProps {
  trustScore: number;
  agentScores: AgentScore[];
  isLive?: boolean;
  className?: string;
  size?: "sm" | "md" | "lg";
}

const AGENT_COLORS: Record<AgentScore["type"], string> = {
  security: "#EF4444",
  compliance: "#F59E0B",
  contextual: "#06B6D4",
  quantum: "#8B5CF6",
  sustainability: "#10B981",
};

const AGENT_LABELS: Record<AgentScore["type"], string> = {
  security: "SEC",
  compliance: "COM",
  contextual: "CTX",
  quantum: "QTM",
  sustainability: "SUS",
};

const SIZE_CONFIG = {
  sm: { center: 60, agent: 30, radius: 100, fontSize: 16 },
  md: { center: 100, agent: 50, radius: 160, fontSize: 24 },
  lg: { center: 120, agent: 60, radius: 200, fontSize: 32 },
};

export default function TrustScoreConstellation({
  trustScore,
  agentScores,
  isLive = false,
  className = "",
  size = "md",
}: TrustScoreConstellationProps) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hoveredAgent, setHoveredAgent] = useState<AgentScore | null>(null);

  const config = SIZE_CONFIG[size];
  const viewBoxSize = config.radius * 2 + config.center + 40;
  const centerX = viewBoxSize / 2;
  const centerY = viewBoxSize / 2;

  // Trust score color based on value
  const getTrustColor = (score: number): string => {
    if (score >= 80) return "#06B6D4"; // Cyan
    if (score >= 50) return "#8B5CF6"; // Violet
    return "#C026D3"; // Fuchsia
  };


  // D3 Constellation Rendering
  useEffect(() => {
    if (!svgRef.current || agentScores.length === 0) return;

    const svg = d3.select(svgRef.current);
    svg.selectAll("*").remove(); // Clear previous render

    // Defs for gradients and filters
    const defs = svg.append("defs");

    // Glow filter for center
    const glowFilter = defs
      .append("filter")
      .attr("id", `glow-${size}`)
      .attr("x", "-50%")
      .attr("y", "-50%")
      .attr("width", "200%")
      .attr("height", "200%");

    glowFilter
      .append("feGaussianBlur")
      .attr("stdDeviation", "4")
      .attr("result", "coloredBlur");

    const glowMerge = glowFilter.append("feMerge");
    glowMerge.append("feMergeNode").attr("in", "coloredBlur");
    glowMerge.append("feMergeNode").attr("in", "SourceGraphic");

    // Connection lines gradient
    const lineGradient = defs
      .append("linearGradient")
      .attr("id", "line-gradient")
      .attr("gradientUnits", "userSpaceOnUse");

    lineGradient
      .append("stop")
      .attr("offset", "0%")
      .attr("stop-color", "#8B5CF6")
      .attr("stop-opacity", 0.6);

    lineGradient
      .append("stop")
      .attr("offset", "100%")
      .attr("stop-color", "#06B6D4")
      .attr("stop-opacity", 0.6);

    // Calculate agent positions (pentagon layout)
    const getAgentPosition = (index: number, total: number) => {
      const angle = (Math.PI * 2 * index) / total - Math.PI / 2;
      return {
        x: centerX + Math.cos(angle) * config.radius,
        y: centerY + Math.sin(angle) * config.radius,
      };
    };

    const agentData = agentScores.map((agent, index) => ({
      ...agent,
      ...getAgentPosition(index, agentScores.length),
    }));

    // Connection lines from agents to center
    const lines = svg
      .append("g")
      .attr("class", "connection-lines")
      .selectAll("line")
      .data(agentData)
      .enter()
      .append("line")
      .attr("x1", (d) => d.x)
      .attr("y1", (d) => d.y)
      .attr("x2", centerX)
      .attr("y2", centerY)
      .attr("stroke", (d) => AGENT_COLORS[d.type])
      .attr("stroke-width", 2)
      .attr("stroke-opacity", 0.4)
      .attr("stroke-dasharray", "4,4");

    // Animate lines on mount
    lines
      .attr("stroke-dashoffset", 100)
      .transition()
      .duration(1000)
      .delay((_, i) => i * 100)
      .attr("stroke-dashoffset", 0);

    // Pulse animation for live state
    if (isLive) {
      lines
        .transition()
        .duration(2000)
        .ease(d3.easeLinear)
        .attr("stroke-opacity", 0.8)
        .transition()
        .duration(2000)
        .ease(d3.easeLinear)
        .attr("stroke-opacity", 0.4)
        .on("end", function repeat() {
          d3.select(this)
            .transition()
            .duration(2000)
            .ease(d3.easeLinear)
            .attr("stroke-opacity", 0.8)
            .transition()
            .duration(2000)
            .ease(d3.easeLinear)
            .attr("stroke-opacity", 0.4)
            .on("end", repeat);
        });
    }

    // Center trust score circle
    const centerGroup = svg.append("g").attr("class", "center-score");

    centerGroup
      .append("circle")
      .attr("cx", centerX)
      .attr("cy", centerY)
      .attr("r", config.center / 2)
      .attr("fill", "url(#center-gradient)")
      .attr("stroke", getTrustColor(trustScore))
      .attr("stroke-width", 3)
      .attr("filter", `url(#glow-${size})`)
      .style("opacity", 0)
      .transition()
      .duration(800)
      .style("opacity", 1);

    // Center gradient
    const centerGradient = defs
      .append("radialGradient")
      .attr("id", "center-gradient");

    centerGradient.append("stop").attr("offset", "0%").attr("stop-color", "#131620");
    centerGradient.append("stop").attr("offset", "100%").attr("stop-color", "#0B0D11");

    // Trust score text
    const scoreText = centerGroup
      .append("text")
      .attr("x", centerX)
      .attr("y", centerY)
      .attr("text-anchor", "middle")
      .attr("dominant-baseline", "middle")
      .attr("fill", getTrustColor(trustScore))
      .attr("font-size", config.fontSize)
      .attr("font-weight", "700")
      .attr("font-family", "Space Grotesk, sans-serif")
      .style("opacity", 0);

    scoreText
      .transition()
      .duration(800)
      .delay(400)
      .style("opacity", 1)
      .tween("text", function () {
        const i = d3.interpolate(0, trustScore);
        return function (t) {
          this.textContent = Math.round(i(t)).toString();
        };
      });

    // "Trust Score" label
    centerGroup
      .append("text")
      .attr("x", centerX)
      .attr("y", centerY + config.fontSize * 0.8)
      .attr("text-anchor", "middle")
      .attr("fill", "#8893AB")
      .attr("font-size", config.fontSize * 0.3)
      .attr("font-weight", "500")
      .attr("font-family", "Inter, sans-serif")
      .style("opacity", 0)
      .text("TRUST SCORE")
      .transition()
      .duration(800)
      .delay(600)
      .style("opacity", 1);

    // Agent nodes
    const agentGroups = svg
      .append("g")
      .attr("class", "agent-nodes")
      .selectAll("g")
      .data(agentData)
      .enter()
      .append("g")
      .attr("transform", (d) => `translate(${d.x},${d.y})`)
      .style("cursor", "pointer")
      .on("mouseenter", (event, d) => setHoveredAgent(d))
      .on("mouseleave", () => setHoveredAgent(null));

    // Agent circles
    agentGroups
      .append("circle")
      .attr("r", 0)
      .attr("fill", "url(#agent-gradient)")
      .attr("stroke", (d) => AGENT_COLORS[d.type])
      .attr("stroke-width", 2)
      .transition()
      .duration(600)
      .delay((_, i) => i * 80 + 400)
      .attr("r", config.agent / 2);

    // Agent gradient
    const agentGradient = defs.append("radialGradient").attr("id", "agent-gradient");

    agentGradient.append("stop").attr("offset", "0%").attr("stop-color", "#1A1F2E");
    agentGradient.append("stop").attr("offset", "100%").attr("stop-color", "#131620");

    // Agent score text
    agentGroups
      .append("text")
      .attr("text-anchor", "middle")
      .attr("dominant-baseline", "middle")
      .attr("fill", "#E8ECF4")
      .attr("font-size", config.fontSize * 0.6)
      .attr("font-weight", "700")
      .attr("font-family", "Space Grotesk, sans-serif")
      .attr("y", -config.fontSize * 0.15)
      .style("opacity", 0)
      .text((d) => Math.round(d.score))
      .transition()
      .duration(600)
      .delay((_, i) => i * 80 + 600)
      .style("opacity", 1);

    // Agent label text
    agentGroups
      .append("text")
      .attr("text-anchor", "middle")
      .attr("dominant-baseline", "middle")
      .attr("fill", "#8893AB")
      .attr("font-size", config.fontSize * 0.25)
      .attr("font-weight", "500")
      .attr("font-family", "JetBrains Mono, monospace")
      .attr("y", config.fontSize * 0.3)
      .style("opacity", 0)
      .text((d) => AGENT_LABELS[d.type])
      .transition()
      .duration(600)
      .delay((_, i) => i * 80 + 700)
      .style("opacity", 1);

    // Hover pulse effect
    agentGroups
      .on("mouseenter", function () {
        d3.select(this)
          .select("circle")
          .transition()
          .duration(200)
          .attr("r", config.agent / 2 + 4)
          .attr("stroke-width", 3);
      })
      .on("mouseleave", function () {
        d3.select(this)
          .select("circle")
          .transition()
          .duration(200)
          .attr("r", config.agent / 2)
          .attr("stroke-width", 2);
      });
  }, [agentScores, trustScore, isLive, size, config, centerX, centerY]);

  return (
    <div className={`relative ${className}`}>
      <svg
        ref={svgRef}
        viewBox={`0 0 ${viewBoxSize} ${viewBoxSize}`}
        className="w-full h-full"
        style={{ maxWidth: "100%", height: "auto" }}
      />

      {/* Tooltip */}
      {hoveredAgent && (
        <div
          className="absolute z-50 glass-elevated rounded-lg p-4 max-w-xs animate-slide-down"
          style={{
            top: "50%",
            left: "50%",
            transform: "translate(-50%, -50%)",
            pointerEvents: "none",
          }}
        >
          <div className="flex items-center gap-2 mb-2">
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: AGENT_COLORS[hoveredAgent.type] }}
            />
            <span className="text-sm font-semibold text-white capitalize">
              {hoveredAgent.type} Agent
            </span>
          </div>
          <div className="text-lg font-bold gradient-text mb-1">
            Score: {Math.round(hoveredAgent.score)}
          </div>
          <p className="text-xs text-gray-400 leading-relaxed">
            {hoveredAgent.rationale}
          </p>
        </div>
      )}

      {/* Live indicator */}
      {isLive && (
        <div className="absolute top-2 right-2 flex items-center gap-2">
          <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse-success" />
          <span className="text-xs text-emerald-400 font-medium uppercase tracking-wider">
            Live
          </span>
        </div>
      )}
    </div>
  );
}
