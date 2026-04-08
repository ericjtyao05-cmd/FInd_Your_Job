"use client";

import { useEffect, useMemo, useState } from "react";

type Language = "en" | "zh";
type RunResponse = { run_id: string; status: string };
type ResumeUploadResponse = { path: string; bucket: string; public_url?: string | null };
type RunDetail = {
  run: Record<string, unknown>;
  events: Array<{
    event_type: string;
    step: string | null;
    payload: Record<string, unknown>;
    created_at: string;
  }>;
  jobs: Array<{
    external_job_id: string;
    title: string;
    company: string;
    location: string;
    source: string;
    url: string;
    category: string;
    fit_score: number | null;
    fit_rationale: string | null;
    review_status: string | null;
    review_notes: string[];
  }>;
  applications: Array<{ job_external_id: string; cover_letter: string }>;
};

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL?.trim() || "http://127.0.0.1:8001";

const COPY = {
  en: {
    langEn: "EN",
    langZh: "中文",
    eyebrow: "Job Match",
    title: "A workspace shaped around the agents doing the work.",
    subtitle: "Each operational agent has its own small window. The review gate gets the large surface so the user can inspect risk before apply.",
    searchInfo: "Search Information",
    formInfo: "Form Information",
    resumeSection: "Resume Upload",
    agentBoard: "Agent Board",
    reviewGate: "Review Gate",
    reviewAction: "User action happens here before anything risky moves forward.",
    targetTitles: "Target Titles",
    preferredLocations: "Preferred Locations",
    name: "Name",
    email: "Email Address",
    phone: "Phone Number",
    experience: "Years of Experience",
    skills: "Skills",
    resumeSummary: "Resume Summary",
    resumeUpload: "Resume File",
    autoSubmit: "Auto Submit",
    startRun: "Start Run",
    starting: "Starting...",
    uploadIdle: "No resume uploaded yet.",
    noResults: "No jobs returned yet.",
    fitPending: "Fit scoring pending.",
    openJob: "Open job",
    statusQueued: "Queued",
    statusRunning: "Running",
    statusCompleted: "Completed",
    statusFailed: "Failed",
    latestStatus: "Latest Run",
    latestStatusIdle: "Not started",
    resultsHint: "Research runs in the background. This board shows each agent as a focused window instead of a long activity feed.",
    reviewEmpty: "No review items yet.",
    selectedJob: "Selected Job",
    researchAgent: "Research Agent",
    fitAgent: "Fit Scoring Agent",
    writerAgent: "Application Writer Agent",
    browserAgent: "Browser Executor Agent",
    researchSummary: "Finds live jobs, filters repeats, and routes them into categories.",
    fitSummary: "Scores each role against your profile and explains the match.",
    writerSummary: "Drafts resume edits, cover letters, and interview prep.",
    browserSummary: "Tracks browser execution readiness and downstream automation results.",
    itemsFound: "jobs found",
    scoredItems: "jobs scored",
    draftedItems: "drafts created",
    browserItems: "browser-ready jobs",
    risks: "Risks",
    notes: "Notes",
    coverLetter: "Cover Letter",
    noCoverLetter: "No draft generated yet.",
    openPosting: "Open posting",
  },
  zh: {
    langEn: "EN",
    langZh: "中文",
    eyebrow: "求职匹配",
    title: "围绕各个智能体工作的界面。",
    subtitle: "每个执行智能体都有自己的小窗口，审核关卡拥有更大的区域，方便用户处理风险内容。",
    searchInfo: "搜索信息",
    formInfo: "表单信息",
    resumeSection: "简历上传",
    agentBoard: "智能体面板",
    reviewGate: "审核关卡",
    reviewAction: "高风险动作进入下一步之前，用户需要在这里处理。",
    targetTitles: "目标职位",
    preferredLocations: "期望地点",
    name: "姓名",
    email: "邮箱地址",
    phone: "电话号码",
    experience: "工作年限",
    skills: "技能",
    resumeSummary: "简历摘要",
    resumeUpload: "简历文件",
    autoSubmit: "自动提交",
    startRun: "开始运行",
    starting: "正在启动...",
    uploadIdle: "尚未上传简历。",
    noResults: "暂时没有返回职位。",
    fitPending: "匹配评分尚未完成。",
    openJob: "打开职位",
    statusQueued: "已排队",
    statusRunning: "运行中",
    statusCompleted: "已完成",
    statusFailed: "失败",
    latestStatus: "最近一次运行",
    latestStatusIdle: "未开始",
    resultsHint: "搜索过程在后台运行。这里将每个智能体显示为独立窗口，而不是冗长的日志流。",
    reviewEmpty: "暂时没有需要审核的内容。",
    selectedJob: "当前职位",
    researchAgent: "研究智能体",
    fitAgent: "匹配评分智能体",
    writerAgent: "申请文书智能体",
    browserAgent: "浏览器执行智能体",
    researchSummary: "抓取实时职位、过滤重复项，并按类别整理结果。",
    fitSummary: "根据你的资料为职位评分，并解释匹配原因。",
    writerSummary: "生成简历修改建议、求职信和问答脚本。",
    browserSummary: "展示浏览器执行准备情况和自动化结果。",
    itemsFound: "个职位",
    scoredItems: "个已评分",
    draftedItems: "份文稿",
    browserItems: "个浏览器任务",
    risks: "风险点",
    notes: "备注",
    coverLetter: "求职信",
    noCoverLetter: "尚未生成文稿。",
    openPosting: "打开职位",
  }
} as const;

export default function Page() {
  const [language, setLanguage] = useState<Language>("en");
  const [runId, setRunId] = useState<string | null>(null);
  const [detail, setDetail] = useState<RunDetail | null>(null);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [resumeUploadState, setResumeUploadState] = useState<string>(COPY.en.uploadIdle);
  const [pageError, setPageError] = useState<string>("");
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [form, setForm] = useState({
    titles: "Software Engineer, Backend Engineer",
    locations: "London, Remote",
    name: "Alex Chen",
    email: "alex.chen@example.com",
    phone: "+44 7700 900123",
    experience: "5",
    skills: "Python, SQL, AWS, Docker, Communication, APIs",
    resumeText: "Experienced engineer with backend and platform delivery experience.",
    allowSubmit: false
  });

  const t = COPY[language];

  useEffect(() => {
    if (!runId) return;
    const timer = setInterval(async () => {
      try {
        const response = await fetch(`${API_BASE}/api/runs/${runId}`);
        if (!response.ok) {
          setPageError(`Failed to load run ${runId}. API responded with ${response.status}.`);
          return;
        }
        const json = (await response.json()) as RunDetail;
        setDetail(json);
        setSelectedJobId((current) => current ?? json.jobs[0]?.external_job_id ?? null);
        setPageError("");
        if (String(json.run.status) === "completed" || String(json.run.status) === "failed") {
          clearInterval(timer);
        }
      } catch (error) {
        setPageError(getErrorMessage(error, "Load failed"));
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [runId]);

  useEffect(() => {
    if (!resumeFile) {
      setResumeUploadState(t.uploadIdle);
    }
  }, [language, resumeFile, t.uploadIdle]);

  async function onSubmit() {
    let resumePath: string | null = null;
    setIsSubmitting(true);
    setPageError("");

    try {
      if (resumeFile) {
        const formData = new FormData();
        formData.append("file", resumeFile);
        setResumeUploadState(`${resumeFile.name}`);
        const uploadResponse = await fetch(`${API_BASE}/api/uploads/resume`, {
          method: "POST",
          body: formData
        });
        if (!uploadResponse.ok) {
          const detail = await uploadResponse.text();
          throw new Error(`Resume upload failed: ${detail}`);
        }
        const upload = (await uploadResponse.json()) as ResumeUploadResponse;
        resumePath = upload.path;
        setResumeUploadState(upload.path);
      }

      const response = await fetch(`${API_BASE}/api/runs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          candidate: {
            name: form.name,
            target_titles: form.titles.split(",").map((value) => value.trim()).filter(Boolean),
            preferred_locations: form.locations.split(",").map((value) => value.trim()).filter(Boolean),
            skills: [
              ...form.skills.split(",").map((value) => value.trim()).filter(Boolean),
              form.email ? `email:${form.email}` : "",
              form.phone ? `phone:${form.phone}` : "",
            ].filter(Boolean),
            years_experience: Number(form.experience || "0"),
            resume_text: form.resumeText,
            resume_file_path: resumePath
          },
          live_research: true,
          allow_submit: form.allowSubmit,
          visual_browser: false,
          top_n: 3
        })
      });

      if (!response.ok) {
        const detail = await response.text();
        throw new Error(`Run creation failed: ${detail}`);
      }

      const json = (await response.json()) as RunResponse;
      setRunId(json.run_id);
      setDetail(null);
      setSelectedJobId(null);
    } catch (error) {
      setPageError(getErrorMessage(error, "Request failed."));
    } finally {
      setIsSubmitting(false);
    }
  }

  const selectedJob = detail?.jobs.find((job) => job.external_job_id === selectedJobId) ?? detail?.jobs[0] ?? null;
  const selectedApplication = detail?.applications.find((app) => app.job_external_id === selectedJob?.external_job_id) ?? null;
  const reviewJobs = useMemo(
    () => (detail?.jobs ?? []).filter((job) => job.review_status || job.review_notes?.length > 0),
    [detail]
  );

  const agentCards = [
    {
      key: "research",
      title: t.researchAgent,
      summary: t.researchSummary,
      value: detail?.jobs.length ?? 0,
      suffix: t.itemsFound,
      state: resolveStepState(detail, "research"),
    },
    {
      key: "fit_scoring",
      title: t.fitAgent,
      summary: t.fitSummary,
      value: (detail?.jobs ?? []).filter((job) => job.fit_score !== null).length,
      suffix: t.scoredItems,
      state: resolveStepState(detail, "fit_scoring"),
    },
    {
      key: "application_writer",
      title: t.writerAgent,
      summary: t.writerSummary,
      value: detail?.applications.length ?? 0,
      suffix: t.draftedItems,
      state: resolveStepState(detail, "application_writer"),
    },
    {
      key: "browser_executor",
      title: t.browserAgent,
      summary: t.browserSummary,
      value: (detail?.jobs ?? []).filter((job) => job.review_status !== "blocked").length,
      suffix: t.browserItems,
      state: resolveStepState(detail, "browser_executor"),
    },
  ];

  return (
    <main className="page">
      <section className="topbar">
        <div className="lang-switch">
          <button className={language === "en" ? "active" : ""} onClick={() => setLanguage("en")}>{t.langEn}</button>
          <button className={language === "zh" ? "active" : ""} onClick={() => setLanguage("zh")}>{t.langZh}</button>
        </div>
      </section>

      <section className="hero panel">
        <div className="hero-copy">
          <div className="eyebrow">{t.eyebrow}</div>
          <h1>{t.title}</h1>
          <p className="subtitle">{t.subtitle}</p>
        </div>
        <div className="status-card">
          <div className="status-label">{t.latestStatus}</div>
          <div className="status-value">{formatRunStatus(String(detail?.run?.status ?? "")) || t.latestStatusIdle}</div>
          <div className="muted">{runId ?? "-"}</div>
        </div>
      </section>

      <section className="content">
        <div className="panel form-panel">
          {pageError && <div className="alert">{pageError}</div>}

          <div className="form-section">
            <h2>{t.searchInfo}</h2>
            <div className="grid two">
              <div className="field">
                <label>{t.targetTitles}</label>
                <input value={form.titles} onChange={(e) => setForm({ ...form, titles: e.target.value })} />
              </div>
              <div className="field">
                <label>{t.preferredLocations}</label>
                <input value={form.locations} onChange={(e) => setForm({ ...form, locations: e.target.value })} />
              </div>
            </div>
          </div>

          <div className="form-section">
            <h2>{t.formInfo}</h2>
            <div className="grid two">
              <div className="field">
                <label>{t.name}</label>
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
              </div>
              <div className="field">
                <label>{t.experience}</label>
                <input value={form.experience} onChange={(e) => setForm({ ...form, experience: e.target.value })} />
              </div>
              <div className="field">
                <label>{t.email}</label>
                <input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
              </div>
              <div className="field">
                <label>{t.phone}</label>
                <input value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })} />
              </div>
              <div className="field full">
                <label>{t.skills}</label>
                <input value={form.skills} onChange={(e) => setForm({ ...form, skills: e.target.value })} />
              </div>
              <div className="field full">
                <label>{t.resumeSummary}</label>
                <textarea value={form.resumeText} onChange={(e) => setForm({ ...form, resumeText: e.target.value })} />
              </div>
            </div>
          </div>

          <div className="form-section">
            <h2>{t.resumeSection}</h2>
            <div className="field">
              <label>{t.resumeUpload}</label>
              <input type="file" onChange={(e) => setResumeFile(e.target.files?.[0] ?? null)} />
              <div className="muted">{resumeUploadState}</div>
            </div>
          </div>

          <div className="actions">
            <label className="check">
              <input type="checkbox" checked={form.allowSubmit} onChange={(e) => setForm({ ...form, allowSubmit: e.target.checked })} />
              {t.autoSubmit}
            </label>
            <button className="button primary" onClick={onSubmit} disabled={isSubmitting}>
              {isSubmitting ? t.starting : t.startRun}
            </button>
          </div>
        </div>

        <div className="panel results-panel">
          <div className="results-head">
            <h2>{t.agentBoard}</h2>
            <div className="muted">{t.resultsHint}</div>
          </div>

          <div className="agent-grid">
            {agentCards.map((card) => (
              <article key={card.key} className="agent-card">
                <div className="agent-card-head">
                  <span className={`agent-state ${card.state}`}>{card.state}</span>
                  <strong>{card.title}</strong>
                </div>
                <div className="agent-metric">{card.value}</div>
                <div className="agent-suffix">{card.suffix}</div>
                <p className="agent-summary">{card.summary}</p>
              </article>
            ))}
          </div>

          <section className="review-window">
            <div className="review-window-head">
              <div>
                <div className="eyebrow">{t.reviewGate}</div>
                <h3>{t.reviewAction}</h3>
              </div>
              <div className={`review-status ${selectedJob?.review_status ?? "idle"}`}>
                {selectedJob?.review_status ?? t.latestStatusIdle}
              </div>
            </div>

            {reviewJobs.length > 0 && (
              <div className="review-job-strip">
                {reviewJobs.map((job) => (
                  <button
                    key={job.external_job_id}
                    className={`review-job-chip ${selectedJob?.external_job_id === job.external_job_id ? "active" : ""}`}
                    onClick={() => setSelectedJobId(job.external_job_id)}
                  >
                    <span>{job.company}</span>
                    <strong>{job.title}</strong>
                  </button>
                ))}
              </div>
            )}

            {selectedJob ? (
              <div className="review-body">
                <div className="review-main">
                  <div className="review-section">
                    <div className="section-label">{t.selectedJob}</div>
                    <div className="job-head large">
                      <strong>{selectedJob.title}</strong>
                      {selectedJob.fit_score !== null && <span className="score">{selectedJob.fit_score}/100</span>}
                    </div>
                    <div className="muted">{selectedJob.company} · {selectedJob.location} · {selectedJob.source}</div>
                    <div className="pillbar">
                      <span className="pill">{selectedJob.category}</span>
                      {selectedJob.review_status && <span className="pill">{selectedJob.review_status}</span>}
                    </div>
                    <div className="review-rationale">{selectedJob.fit_rationale ?? t.fitPending}</div>
                    <div className="job-link">
                      <a href={selectedJob.url} target="_blank" rel="noreferrer">{t.openPosting}</a>
                    </div>
                  </div>

                  <div className="review-section">
                    <div className="section-label">{t.coverLetter}</div>
                    <div className="cover-letter-box">
                      {selectedApplication?.cover_letter ?? t.noCoverLetter}
                    </div>
                  </div>
                </div>

                <aside className="review-side">
                  <div className="review-section">
                    <div className="section-label">{t.risks}</div>
                    <div className="stack-list">
                      {selectedJob.review_notes?.length > 0 ? (
                        selectedJob.review_notes.map((note, index) => (
                          <div key={`${selectedJob.external_job_id}-risk-${index}`} className="stack-item">{note}</div>
                        ))
                      ) : (
                        <div className="empty compact">{t.reviewEmpty}</div>
                      )}
                    </div>
                  </div>

                  <div className="review-section">
                    <div className="section-label">{t.notes}</div>
                    <div className="stack-list">
                      {(detail?.events ?? [])
                        .filter((event) => event.step === "review_gate" || event.step === "browser_executor")
                        .slice(-4)
                        .map((event, index) => (
                          <div key={`${event.created_at}-${index}`} className="stack-item">
                            {String(event.payload.message ?? event.event_type)}
                          </div>
                        ))}
                    </div>
                  </div>
                </aside>
              </div>
            ) : (
              <div className="empty">{detail ? t.reviewEmpty : t.noResults}</div>
            )}
          </section>
        </div>
      </section>
    </main>
  );
}

function resolveStepState(detail: RunDetail | null, step: string): string {
  if (!detail) return "idle";
  if (String(detail.run.status) === "failed") return "failed";
  const matched = detail.events.filter((event) => event.step === step);
  if (matched.length > 0) return "done";
  if (String(detail.run.status) === "running" || String(detail.run.status) === "queued") return "working";
  return "idle";
}

function formatRunStatus(status: string): string {
  if (status === "queued") return "Queued";
  if (status === "running") return "Running";
  if (status === "completed") return "Completed";
  if (status === "failed") return "Failed";
  return "";
}

function getErrorMessage(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}
