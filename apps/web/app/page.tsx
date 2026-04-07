"use client";

import { useEffect, useState } from "react";

type Language = "en" | "zh";
type RunResponse = { run_id: string; status: string };
type ResumeUploadResponse = { path: string; bucket: string; public_url?: string | null };
type RunDetail = {
  run: Record<string, unknown>;
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
    title: "Search and apply with a cleaner workflow.",
    subtitle: "Tell the system what roles to search for, what information to use in applications, and upload the resume once.",
    searchInfo: "Search Information",
    formInfo: "Form Information",
    resumeSection: "Resume Upload",
    results: "Matched Jobs",
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
    resultsHint: "The search process is hidden. Results will appear here when the run returns.",
  },
  zh: {
    langEn: "EN",
    langZh: "中文",
    eyebrow: "求职匹配",
    title: "用更简洁的流程完成搜索与申请。",
    subtitle: "告诉系统你想找什么岗位、申请表需要填写什么信息，并上传一次简历即可。",
    searchInfo: "搜索信息",
    formInfo: "表单信息",
    resumeSection: "简历上传",
    results: "匹配结果",
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
    resultsHint: "搜索过程不会展示给用户，结果会直接显示在这里。",
  }
} as const;

export default function Page() {
  const [language, setLanguage] = useState<Language>("en");
  const [runId, setRunId] = useState<string | null>(null);
  const [detail, setDetail] = useState<RunDetail | null>(null);
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
    } catch (error) {
      setPageError(getErrorMessage(error, "Request failed."));
    } finally {
      setIsSubmitting(false);
    }
  }

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
            <h2>{t.results}</h2>
            <div className="muted">{t.resultsHint}</div>
          </div>
          <div className="jobs">
            {(detail?.jobs ?? []).map((job) => (
              <article key={job.external_job_id} className="job">
                <div className="job-head">
                  <strong>{job.title}</strong>
                  {job.fit_score !== null && <span className="score">{job.fit_score}/100</span>}
                </div>
                <div className="muted">{job.company} · {job.location} · {job.source}</div>
                <div className="pillbar">
                  <span className="pill">{job.category}</span>
                  {job.review_status && <span className="pill">{job.review_status}</span>}
                </div>
                <div>{job.fit_rationale ?? t.fitPending}</div>
                {job.review_notes?.length > 0 && <div className="muted">{job.review_notes.join(" | ")}</div>}
                <div className="job-link">
                  <a href={job.url} target="_blank" rel="noreferrer">{t.openJob}</a>
                </div>
              </article>
            ))}
            {detail && detail.jobs.length === 0 && <div className="empty">{t.noResults}</div>}
            {!detail && <div className="empty">{t.noResults}</div>}
          </div>
        </div>
      </section>
    </main>
  );
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
