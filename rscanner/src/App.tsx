import { useState, useCallback, useEffect, useRef } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { NameInput } from "./components/NameInput";
import { ActionBar } from "./components/ActionBar";
import { StatsPanel } from "./components/StatsPanel";
import { PhaseProgress } from "./components/PhaseProgress";
import { ResultTree } from "./components/ResultTree";
import { ContextMenu } from "./components/ContextMenu";
import { StatusBar } from "./components/StatusBar";
import { Sidebar } from "./components/Sidebar";

export interface DetectionResult {
  file_type: string;
  path: string;
  filename: string;
  size: number;
  source: string;
}

export interface ProgressEvent {
  scanned: number;
  found: number;
  speed: number;
  elapsed_secs: number;
  phase: ScanPhase;
}

type ScanPhase = "Idle" | "Registry" | "FixedPaths" | "FullScan" | "Complete";

function App() {
  const [name, setName] = useState("");
  const [phase, setPhase] = useState<ScanPhase>("Idle");
  const [progress, setProgress] = useState({ scanned: 0, found: 0, speed: 0, elapsed: 0 });
  const [results, setResults] = useState<DetectionResult[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [drives, setDrives] = useState<string[]>([]);
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; path: string } | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [isScanning, setIsScanning] = useState(false);

  const nameRef = useRef(name);
  nameRef.current = name;

  const addLog = useCallback((msg: string) => {
    setLogs((prev) => [...prev.slice(-99), `[${new Date().toLocaleTimeString()}] ${msg}`]);
  }, []);

  useEffect(() => {
    invoke<string[]>("get_drives").then(setDrives);

    const unlistenProgress = listen<ProgressEvent>("scan-progress", (e) => {
      setProgress({
        scanned: e.payload.scanned,
        found: e.payload.found,
        speed: e.payload.speed,
        elapsed: e.payload.elapsed_secs,
      });
    });

    const unlistenPhase = listen<{ phase: ScanPhase }>("scan-phase", (e) => {
      setPhase(e.payload.phase);
      addLog(`阶段切换: ${e.payload.phase}`);
    });

    const unlistenComplete = listen<{ total_found: number; results: DetectionResult[] }>(
      "scan-complete",
      (e) => {
        setResults(e.payload.results);
        setPhase("Complete");
        setIsScanning(false);
        addLog(`扫描完成，发现 ${e.payload.total_found} 项`);

        // 有结果时自动上报
        if (e.payload.results.length > 0) {
          addLog("正在获取位置信息...");
          invoke<string>("get_city_from_ip").then((city) => {
            addLog(`位置: ${city}`);
            addLog("正在自动上报...");
            return invoke("send_report", { name: nameRef.current, results: e.payload.results, city });
          }).then(() => {
            addLog("上报完成");
          }).catch((err) => {
            addLog(`上报失败: ${err}`);
          });
        }
      }
    );

    return () => {
      unlistenProgress.then((f) => f());
      unlistenPhase.then((f) => f());
      unlistenComplete.then((f) => f());
    };
  }, []);

  const handleStart = useCallback(async () => {
    if (!name.trim()) return;
    setIsScanning(true);
    setResults([]);
    setSelected(new Set());
    setProgress({ scanned: 0, found: 0, speed: 0, elapsed: 0 });
    addLog(`开始扫描: ${name}`);
    try {
      await invoke("start_scan", { name, drives });
    } catch (e) {
      addLog(`扫描失败: ${e}`);
      setIsScanning(false);
    }
  }, [name, drives]);

  const handleCancel = useCallback(async () => {
    await invoke("cancel_scan");
    setIsScanning(false);
    addLog("扫描已取消");
  }, []);

  const handleDelete = useCallback(async () => {
    if (selected.size === 0) return;
    const paths = Array.from(selected);
    addLog(`删除 ${paths.length} 项`);
    const results = await invoke<{ path: string; success: boolean; error?: string }[]>(
      "delete_files", { paths }
    );
    const failed = results.filter((r) => !r.success);
    if (failed.length > 0) {
      addLog(`删除失败 ${failed.length} 项`);
    }
    setResults((prev) => prev.filter((r) => !selected.has(r.path)));
    setSelected(new Set());
  }, [selected]);

  const handleSelectAll = useCallback(() => {
    setSelected(new Set(results.map((r) => r.path)));
  }, [results]);

  const handleDeselectAll = useCallback(() => {
    setSelected(new Set());
  }, []);

  const handleCleanRegistry = useCallback(async () => {
    addLog("清理注册表...");
    const result = await invoke<{ deleted: number; errors: string[] }>("clean_registry");
    addLog(`注册表清理完成，删除 ${result.deleted} 项`);
    if (result.errors.length > 0) {
      result.errors.forEach((e) => addLog(`错误: ${e}`));
    }
  }, []);

  const handleCopyPaths = useCallback(async () => {
    const paths = Array.from(selected);
    if (paths.length === 0) return;
    await navigator.clipboard.writeText(paths.join("\n"));
    addLog(`已复制 ${paths.length} 个路径`);
  }, [selected]);

  const handleOpenInExplorer = useCallback(async (path: string) => {
    await invoke("open_in_explorer", { path });
  }, []);

  const handleSendReport = useCallback(async () => {
    if (!name.trim()) return;
    addLog("正在上报...");
    try {
      await invoke("send_report", { name, results });
      addLog("上报完成");
    } catch (e) {
      addLog(`上报失败: ${e}`);
    }
  }, [name, results]);

  const stats = {
    installers: results.filter((r) => r.file_type === "安装程序").length,
    logs: results.filter((r) => r.file_type === "日志/文本").length,
    documents: results.filter((r) => r.file_type === "文档").length,
    registry: results.filter((r) => r.source === "注册表扫描").length,
  };

  return (
    <div className="h-screen flex flex-col bg-[#131313]">
      {/* Header */}
      <header className="flex items-center gap-4 px-5 py-3 bg-[#1b1b1c] border-b border-[#2a2a2a]">
        <h1 className="text-lg font-semibold text-[#e5e2e1]">违规软件内容检测器</h1>
        <div className="flex-1" />
        <NameInput value={name} onChange={setName} disabled={isScanning} />
        <ActionBar
          isScanning={isScanning}
          hasResults={results.length > 0}
          hasSelection={selected.size > 0}
          onStart={handleStart}
          onCancel={handleCancel}
          onDelete={handleDelete}
          onSelectAll={handleSelectAll}
          onDeselectAll={handleDeselectAll}
          onCopyPaths={handleCopyPaths}
          onCleanRegistry={handleCleanRegistry}
          onSendReport={handleSendReport}
        />
      </header>

      {/* Main content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <Sidebar
          stats={stats}
          totalFound={results.length}
          logs={logs}
        />

        {/* Main area */}
        <main className="flex-1 flex flex-col overflow-hidden">
          {/* Progress section */}
          <StatsPanel
            scanned={progress.scanned}
            found={progress.found}
            speed={progress.speed}
            elapsed={progress.elapsed}
          />
          <PhaseProgress phase={phase} />

          {/* Results tree */}
          <div className="flex-1 overflow-auto px-4 pb-2">
            {results.length > 0 ? (
              <ResultTree
                results={results}
                selected={selected}
                onToggle={(path) => {
                  setSelected((prev) => {
                    const next = new Set(prev);
                    if (next.has(path)) next.delete(path);
                    else next.add(path);
                    return next;
                  });
                }}
                onContextMenu={(e, path) => {
                  e.preventDefault();
                  setContextMenu({ x: e.clientX, y: e.clientY, path });
                }}
                onOpenInExplorer={handleOpenInExplorer}
              />
            ) : (
              <div className="flex items-center justify-center h-full text-[#8a919e] text-sm">
                {phase === "Idle" ? "输入姓名后点击 ▶ 开始检测" : "暂无结果"}
              </div>
            )}
          </div>
        </main>
      </div>

      {/* Context menu */}
      {contextMenu && (
        <ContextMenu
          x={contextMenu.x}
          y={contextMenu.y}
          path={contextMenu.path}
          onClose={() => setContextMenu(null)}
          onOpenInExplorer={handleOpenInExplorer}
          onCopy={async (path) => {
            await navigator.clipboard.writeText(path);
            addLog("已复制路径");
            setContextMenu(null);
          }}
        />
      )}

      {/* Status bar */}
      <StatusBar
        phase={phase}
        selectedCount={selected.size}
        totalCount={results.length}
      />
    </div>
  );
}

export default App;
