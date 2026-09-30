import { useEffect, useState } from 'react';
import { ReportsService, type FabReport } from '@/services/ReportsService';
import { GlassCard } from '@/components/shared/GlassCard';
import { Button } from '@/components/ui/button';
import { 
  FileText, 
  Plus, 
  Search, 
  Clock, 
  DollarSign, 
  ShieldCheck, 
  FileSpreadsheet, 
  FileCode,
  Sparkles
} from 'lucide-react';

export default function ReportsPage() {
  const [reports, setReports] = useState<FabReport[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [typeFilter, setTypeFilter] = useState('ALL');
  const [isGenerating, setIsGenerating] = useState(false);
  const [selectedReport, setSelectedReport] = useState<FabReport | null>(null);

  const loadReports = async () => {
    const data = await ReportsService.getReports();
    setReports(data);
    if (data.length > 0 && !selectedReport) {
      setSelectedReport(data[0]);
    }
  };

  useEffect(() => {
    loadReports();
  }, []);

  const handleGenerate = async () => {
    setIsGenerating(true);
    try {
      const rep = await ReportsService.generateNewReport('Executive', 'Full Fab Horizon');
      setReports((prev) => [rep, ...prev]);
      setSelectedReport(rep);
    } finally {
      setIsGenerating(false);
    }
  };

  const filtered = reports.filter((r) => {
    const matchesSearch = r.title.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          r.summary.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          r.id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = typeFilter === 'ALL' || r.type === typeFilter;
    return matchesSearch && matchesType;
  });

  return (
    <div className="flex flex-col gap-6 animate-in fade-in slide-in-from-bottom-4 duration-500 max-w-7xl mx-auto">
      
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-foreground">Operational Reports & Audits</h1>
          <p className="text-muted-foreground text-sm">
            Generate, review, and export official semiconductor manufacturing schedules and shift audits.
          </p>
        </div>

        <Button 
          variant="glow" 
          onClick={handleGenerate} 
          disabled={isGenerating}
          className="flex items-center gap-2 self-start sm:self-auto font-semibold px-5"
        >
          {isGenerating ? (
            <>
              <Sparkles className="w-4 h-4 animate-spin text-primary" />
              Compiling Live Report...
            </>
          ) : (
            <>
              <Plus className="w-4 h-4" />
              Generate Shift Report
            </>
          )}
        </Button>
      </div>

      {/* Top Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <GlassCard className="p-5 flex items-center gap-4">
          <div className="p-3 rounded-xl bg-primary/10 border border-primary/20 text-primary">
            <FileText className="w-6 h-6" />
          </div>
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider">Total Audits</div>
            <div className="text-2xl font-bold text-foreground">{reports.length} Available</div>
            <div className="text-[11px] text-muted-foreground">Certified SMT2020 Logs</div>
          </div>
        </GlassCard>

        <GlassCard className="p-5 flex items-center gap-4">
          <div className="p-3 rounded-xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider">Average Compliance</div>
            <div className="text-2xl font-bold text-emerald-400">99.5% On-Time</div>
            <div className="text-[11px] text-muted-foreground">Zero Contractual Breach</div>
          </div>
        </GlassCard>

        <GlassCard className="p-5 flex items-center gap-4">
          <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-amber-400">
            <DollarSign className="w-6 h-6" />
          </div>
          <div>
            <div className="text-xs text-muted-foreground uppercase tracking-wider">Cumulative Penalties Avoided</div>
            <div className="text-2xl font-bold text-foreground">$31,600</div>
            <div className="text-[11px] text-emerald-400 font-medium">Audited & Approved</div>
          </div>
        </GlassCard>
      </div>

      {/* Filter and Search Bar */}
      <div className="flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search audits by title, keyword, ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 rounded-xl bg-white/5 border border-white/10 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:border-primary/50 transition-colors"
          />
        </div>

        <div className="flex items-center gap-2 overflow-x-auto w-full sm:w-auto pb-1 sm:pb-0">
          {['ALL', 'Executive', 'Shift Handover', 'Compliance', 'Maintenance'].map((t) => (
            <button
              key={t}
              onClick={() => setTypeFilter(t)}
              className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all whitespace-nowrap cursor-pointer ${
                typeFilter === t
                  ? 'bg-primary text-primary-foreground font-semibold shadow-[0_0_12px_rgba(56,189,248,0.4)]'
                  : 'bg-white/5 text-muted-foreground hover:text-foreground hover:bg-white/10 border border-white/5'
              }`}
            >
              {t}
            </button>
          ))}
        </div>
      </div>

      {/* Reports Grid / Master-Detail view */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Reports List (2 cols) */}
        <div className="lg:col-span-2 space-y-4">
          {filtered.map((report) => (
            <GlassCard
              key={report.id}
              onClick={() => setSelectedReport(report)}
              className={`p-5 cursor-pointer transition-all duration-200 border ${
                selectedReport?.id === report.id
                  ? 'border-primary/50 bg-white/[0.08] shadow-[0_0_20px_-5px_rgba(56,189,248,0.3)]'
                  : 'hover:border-white/20'
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-2">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs font-bold text-primary">{report.id}</span>
                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold uppercase bg-white/5 border border-white/10 text-muted-foreground">
                    {report.type}
                  </span>
                  <span className="text-xs text-muted-foreground">• {report.shift}</span>
                </div>
                <div className="text-xs text-muted-foreground flex items-center gap-1 font-mono">
                  <Clock className="w-3 h-3 text-muted-foreground" />
                  {report.generatedAt}
                </div>
              </div>

              <h3 className="text-base font-semibold text-foreground mb-1">{report.title}</h3>
              <p className="text-xs text-muted-foreground line-clamp-2 mb-4">{report.summary}</p>

              {/* Metrics row */}
              <div className="grid grid-cols-4 gap-2 pt-3 border-t border-white/5 text-xs">
                <div>
                  <span className="text-muted-foreground block text-[10px] uppercase">Makespan</span>
                  <span className="font-mono font-medium text-foreground">{report.metrics.makespanHours}h</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[10px] uppercase">Lots</span>
                  <span className="font-mono font-medium text-foreground">{report.metrics.totalLotsScheduled}</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[10px] uppercase">On-Time</span>
                  <span className="font-mono font-medium text-emerald-400">{report.metrics.onTimeRatePct}%</span>
                </div>
                <div>
                  <span className="text-muted-foreground block text-[10px] uppercase">Saved</span>
                  <span className="font-mono font-medium text-emerald-400">
                    ${report.metrics.totalPenaltiesAvoided.toLocaleString()}
                  </span>
                </div>
              </div>
            </GlassCard>
          ))}
        </div>

        {/* Selected Report Details & Export Drawer (1 col) */}
        <div className="lg:col-span-1">
          {selectedReport ? (
            <GlassCard className="p-6 sticky top-24 space-y-6">
              <div>
                <div className="flex items-center justify-between mb-2">
                  <span className="font-mono text-xs font-bold text-primary">{selectedReport.id}</span>
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-semibold uppercase bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                    {selectedReport.status}
                  </span>
                </div>
                <h2 className="text-lg font-bold text-foreground mb-1">{selectedReport.title}</h2>
                <div className="text-xs text-muted-foreground">Author: {selectedReport.author}</div>
              </div>

              <div className="p-3 rounded-xl bg-white/5 border border-white/10 text-xs text-muted-foreground leading-relaxed">
                {selectedReport.summary}
              </div>

              <div className="space-y-3">
                <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider">Audit Key Figures</h4>
                <div className="space-y-2 text-xs">
                  <div className="flex justify-between py-1.5 border-b border-white/5">
                    <span className="text-muted-foreground">Operating Shift:</span>
                    <span className="font-medium text-foreground">{selectedReport.shift}</span>
                  </div>
                  <div className="flex justify-between py-1.5 border-b border-white/5">
                    <span className="text-muted-foreground">Makespan Horizon:</span>
                    <span className="font-mono font-medium text-foreground">{selectedReport.metrics.makespanHours} Hours</span>
                  </div>
                  <div className="flex justify-between py-1.5 border-b border-white/5">
                    <span className="text-muted-foreground">Wafers/Lots Scheduled:</span>
                    <span className="font-mono font-medium text-foreground">{selectedReport.metrics.totalLotsScheduled} Lots</span>
                  </div>
                  <div className="flex justify-between py-1.5 border-b border-white/5">
                    <span className="text-muted-foreground">Contractual SLA Rate:</span>
                    <span className="font-mono font-medium text-emerald-400">{selectedReport.metrics.onTimeRatePct}% Delivery</span>
                  </div>
                  <div className="flex justify-between py-1.5">
                    <span className="text-muted-foreground">Avoided Penalty Cost:</span>
                    <span className="font-mono font-medium text-emerald-400">
                      ${selectedReport.metrics.totalPenaltiesAvoided.toLocaleString()}
                    </span>
                  </div>
                </div>
              </div>

              {/* Export actions */}
              <div className="space-y-2 pt-2 border-t border-white/10">
                <h4 className="text-xs font-semibold text-foreground uppercase tracking-wider mb-2">Export Data</h4>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => ReportsService.exportToCsv(selectedReport)}
                    className="flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-medium text-foreground transition-all cursor-pointer"
                  >
                    <FileSpreadsheet className="w-4 h-4 text-emerald-400" />
                    Export CSV
                  </button>
                  <button
                    onClick={() => ReportsService.exportToJson(selectedReport)}
                    className="flex items-center justify-center gap-2 py-2.5 px-3 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-medium text-foreground transition-all cursor-pointer"
                  >
                    <FileCode className="w-4 h-4 text-primary" />
                    Export JSON
                  </button>
                </div>
              </div>

            </GlassCard>
          ) : (
            <GlassCard className="p-8 text-center text-muted-foreground text-sm">
              Select an audit report to view details and export data.
            </GlassCard>
          )}
        </div>

      </div>

    </div>
  );
}
