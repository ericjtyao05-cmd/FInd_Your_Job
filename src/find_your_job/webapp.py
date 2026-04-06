from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import asdict
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from queue import Empty, Queue
from urllib.parse import urlparse

from find_your_job.browser_adapters import BrowserTaskBuilder
from find_your_job.models import CandidateProfile
from find_your_job.orchestrator import JobMatchSystem, WorkflowConfig
from find_your_job.sample_data import sample_candidate, sample_jobs, sample_research_sources


INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Find Your Job</title>
  <style>
    :root {
      --bg: #f4efe6;
      --panel: rgba(255, 252, 247, 0.92);
      --ink: #1d2433;
      --muted: #5a6478;
      --line: #d8cdb7;
      --accent: #b6562c;
      --accent-soft: #f0d5c7;
      --ok: #1f7a4f;
      --warn: #b06a00;
      --bad: #9f2d2d;
      --shadow: 0 18px 60px rgba(48, 37, 18, 0.12);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Georgia, "Iowan Old Style", "Palatino Linotype", serif;
      color: var(--ink);
      background:
        radial-gradient(circle at top left, rgba(182, 86, 44, 0.14), transparent 32%),
        radial-gradient(circle at top right, rgba(31, 122, 79, 0.11), transparent 30%),
        linear-gradient(180deg, #f9f4ea 0%, var(--bg) 100%);
    }
    .shell {
      max-width: 1300px;
      margin: 0 auto;
      padding: 32px 20px 56px;
    }
    .hero {
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 24px;
      margin-bottom: 24px;
    }
    .panel {
      background: var(--panel);
      border: 1px solid rgba(216, 205, 183, 0.9);
      border-radius: 22px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(8px);
    }
    .hero-copy {
      padding: 28px;
      position: relative;
      overflow: hidden;
    }
    .hero-copy::after {
      content: "";
      position: absolute;
      width: 180px;
      height: 180px;
      right: -40px;
      top: -60px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(182, 86, 44, 0.18), transparent 70%);
    }
    .topbar {
      display: flex;
      justify-content: flex-end;
      margin-bottom: 12px;
    }
    .lang-switch {
      display: inline-flex;
      padding: 4px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255,255,255,0.56);
      gap: 4px;
    }
    .lang-switch button {
      padding: 8px 12px;
      border-radius: 999px;
      border: 0;
      background: transparent;
      color: var(--muted);
    }
    .lang-switch button.active {
      background: var(--accent);
      color: #fff8f4;
    }
    h1 {
      margin: 0 0 10px;
      font-size: clamp(2.4rem, 4vw, 4rem);
      line-height: 0.95;
      letter-spacing: -0.04em;
    }
    .subtitle {
      margin: 0;
      max-width: 48rem;
      color: var(--muted);
      font-size: 1.05rem;
      line-height: 1.5;
    }
    .stats {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 12px;
      margin-top: 28px;
    }
    .stat {
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px;
      background: rgba(255,255,255,0.35);
    }
    .stat .label { color: var(--muted); font-size: 0.84rem; }
    .stat .value { font-size: 1.4rem; margin-top: 4px; }
    .control-card {
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }
    .grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 18px;
    }
    .field {
      display: flex;
      flex-direction: column;
      gap: 8px;
    }
    .field.full { grid-column: 1 / -1; }
    label {
      font-size: 0.84rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
    }
    input, textarea {
      width: 100%;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.78);
      border-radius: 14px;
      padding: 12px 14px;
      color: var(--ink);
      font: inherit;
    }
    textarea { min-height: 92px; resize: vertical; }
    .inline {
      display: flex;
      gap: 12px;
      align-items: center;
      flex-wrap: wrap;
    }
    .check {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 0.95rem;
    }
    .check input {
      width: auto;
      accent-color: var(--accent);
    }
    .file-note {
      color: var(--muted);
      font-size: 0.9rem;
    }
    button {
      border: 0;
      border-radius: 999px;
      padding: 13px 18px;
      font: inherit;
      cursor: pointer;
      transition: transform 120ms ease, opacity 120ms ease;
    }
    button:hover { transform: translateY(-1px); }
    button:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
    .primary {
      background: var(--accent);
      color: #fff8f4;
    }
    .secondary {
      background: transparent;
      color: var(--ink);
      border: 1px solid var(--line);
    }
    .main {
      display: grid;
      grid-template-columns: 0.9fr 1.1fr;
      gap: 24px;
    }
    .timeline, .results {
      padding: 22px;
    }
    .section-title {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 16px;
    }
    .section-title h2 {
      margin: 0;
      font-size: 1.15rem;
      letter-spacing: -0.02em;
    }
    .badge {
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 0.78rem;
      background: var(--accent-soft);
      color: var(--accent);
    }
    .steps {
      display: grid;
      gap: 12px;
    }
    .step {
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 14px;
      background: rgba(255,255,255,0.42);
    }
    .step header {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      margin-bottom: 6px;
    }
    .step h3 {
      margin: 0;
      font-size: 1rem;
    }
    .status {
      font-size: 0.78rem;
      border-radius: 999px;
      padding: 4px 9px;
      border: 1px solid currentColor;
    }
    .status.pending { color: var(--muted); }
    .status.running { color: var(--warn); }
    .status.done { color: var(--ok); }
    .status.failed { color: var(--bad); }
    .step p {
      margin: 0;
      color: var(--muted);
      line-height: 1.45;
    }
    .feed {
      display: grid;
      gap: 10px;
      max-height: 320px;
      overflow: auto;
      padding-right: 4px;
    }
    .feed-item {
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.42);
      font-size: 0.95rem;
      line-height: 1.45;
    }
    .cards {
      display: grid;
      gap: 14px;
    }
    .job-card {
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 16px;
      background: rgba(255,255,255,0.5);
    }
    .job-card h3 {
      margin: 0 0 4px;
      font-size: 1.05rem;
    }
    .meta {
      color: var(--muted);
      font-size: 0.92rem;
      margin-bottom: 10px;
    }
    .pill-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      margin: 10px 0;
    }
    .pill {
      padding: 6px 10px;
      border-radius: 999px;
      background: rgba(182, 86, 44, 0.1);
      color: var(--accent);
      font-size: 0.82rem;
    }
    .job-card a {
      color: var(--accent);
      text-decoration: none;
      font-weight: 600;
    }
    .browser-grid {
      display: grid;
      gap: 12px;
      margin-top: 18px;
    }
    .browser-shot {
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 12px;
      background: rgba(255,255,255,0.42);
    }
    .browser-shot img {
      width: 100%;
      border-radius: 12px;
      display: block;
      margin-top: 8px;
    }
    .empty {
      padding: 18px;
      border: 1px dashed var(--line);
      border-radius: 16px;
      color: var(--muted);
      background: rgba(255,255,255,0.32);
    }
    @media (max-width: 980px) {
      .hero, .main, .grid { grid-template-columns: 1fr; }
      .stats { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="shell">
    <div class="topbar">
      <div class="lang-switch" aria-label="Language switch">
        <button id="lang-en" class="active" type="button">EN</button>
        <button id="lang-zh" type="button">中文</button>
      </div>
    </div>
    <section class="hero">
      <div class="panel hero-copy">
        <div class="badge" data-i18n="hero_badge">Visible Multi-Agent Workflow</div>
        <h1 data-i18n="hero_title">See each agent think through the job hunt.</h1>
        <p class="subtitle" data-i18n="hero_subtitle">
          This UI runs the research, scoring, writing, browser, and review agents step by step.
          You can watch progress live instead of waiting for one final JSON dump.
        </p>
        <div class="stats">
          <div class="stat"><div class="label" data-i18n="stat_research_label">Research Sources</div><div class="value" data-i18n="stat_research_value">Lever + Greenhouse</div></div>
          <div class="stat"><div class="label" data-i18n="stat_browser_label">Browser Mode</div><div class="value" data-i18n="stat_browser_value">Playwright</div></div>
          <div class="stat"><div class="label" data-i18n="stat_review_label">Review Gate</div><div class="value" data-i18n="stat_review_value">Human Confirmation</div></div>
        </div>
      </div>
      <div class="panel control-card">
        <div class="grid">
          <div class="field">
            <label for="name" data-i18n="label_name">Name</label>
            <input id="name" value="Alex Chen">
          </div>
          <div class="field">
            <label for="experience" data-i18n="label_experience">Years Experience</label>
            <input id="experience" type="number" min="0" value="5">
          </div>
          <div class="field full">
            <label for="titles" data-i18n="label_titles">Target Titles</label>
            <input id="titles" value="Software Engineer, Backend Engineer">
          </div>
          <div class="field full">
            <label for="locations" data-i18n="label_locations">Preferred Locations</label>
            <input id="locations" value="London, Remote">
          </div>
          <div class="field full">
            <label for="skills" data-i18n="label_skills">Skills</label>
            <input id="skills" value="Python, SQL, AWS, Docker, Communication, APIs">
          </div>
          <div class="field full">
            <label for="resume_file" data-i18n="label_resume_file">Resume File</label>
            <input id="resume_file" type="file" accept=".pdf,.doc,.docx,.txt">
            <div id="resume-file-note" class="file-note" data-i18n="resume_file_note">No file selected. The server will store uploaded resumes under artifacts/uploads.</div>
          </div>
          <div class="field full">
            <label for="resume_text" data-i18n="label_resume_text">Resume Summary</label>
            <textarea id="resume_text">Experienced engineer with backend and platform delivery experience.</textarea>
          </div>
        </div>
        <div class="inline">
          <label class="check"><input id="live_research" type="checkbox" checked><span data-i18n="toggle_live_research">Use live research sources</span></label>
          <label class="check"><input id="allow_submit" type="checkbox"><span data-i18n="toggle_allow_submit">Allow final submit</span></label>
          <label class="check"><input id="visual_browser" type="checkbox"><span data-i18n="toggle_visual_browser">Visual browser mode</span></label>
        </div>
        <div class="inline">
          <button id="run" class="primary" data-i18n="button_run">Run Workflow</button>
          <button id="reset" class="secondary" data-i18n="button_reset">Reset View</button>
        </div>
      </div>
    </section>

    <section class="main">
      <div class="panel timeline">
        <div class="section-title">
          <h2 data-i18n="timeline_title">Agent Timeline</h2>
          <span id="run-status" class="badge">Idle</span>
        </div>
        <div id="steps" class="steps"></div>
        <h2 style="margin:22px 0 12px;" data-i18n="feed_title">Live Feed</h2>
        <div id="feed" class="feed"></div>
        <h2 style="margin:22px 0 12px;" data-i18n="browser_feed_title">Browser Activity</h2>
        <div id="browser-feed" class="feed"></div>
      </div>

      <div class="panel results">
        <div class="section-title">
          <h2 data-i18n="results_title">Results</h2>
          <span id="summary" class="badge">No run yet</span>
        </div>
        <div id="jobs" class="cards">
          <div class="empty" data-i18n="empty_initial">Start a run to see discovered jobs, fit scores, review blockers, and generated application assets.</div>
        </div>
        <div id="browser-shots" class="browser-grid"></div>
      </div>
    </section>
  </div>

  <script>
    const translations = {
      en: {
        hero_badge: "Visible Multi-Agent Workflow",
        hero_title: "See each agent think through the job hunt.",
        hero_subtitle: "This UI runs the research, scoring, writing, browser, and review agents step by step. You can watch progress live instead of waiting for one final JSON dump.",
        stat_research_label: "Research Sources",
        stat_research_value: "Lever + Greenhouse",
        stat_browser_label: "Browser Mode",
        stat_browser_value: "Playwright",
        stat_review_label: "Review Gate",
        stat_review_value: "Human Confirmation",
        label_name: "Name",
        label_experience: "Years Experience",
        label_titles: "Target Titles",
        label_locations: "Preferred Locations",
        label_skills: "Skills",
        label_resume_file: "Resume File",
        resume_file_note: "No file selected. The server will store uploaded resumes under artifacts/uploads.",
        label_resume_text: "Resume Summary",
        toggle_live_research: "Use live research sources",
        toggle_allow_submit: "Allow final submit",
        toggle_visual_browser: "Visual browser mode",
        button_run: "Run Workflow",
        button_reset: "Reset View",
        timeline_title: "Agent Timeline",
        feed_title: "Live Feed",
        browser_feed_title: "Browser Activity",
        results_title: "Results",
        empty_initial: "Start a run to see discovered jobs, fit scores, review blockers, and generated application assets.",
        empty_no_jobs: "No jobs matched the current filters. Try broader titles or locations.",
        browser_no_activity: "Browser actions and screenshots will appear here during execution.",
        browser_session_start: "Browser executor starting in {mode} mode.",
        browser_session_launch_ok: "Chromium launched successfully.",
        browser_open_page: "Opening application page: {url}",
        browser_wait_marker: "Waiting for page marker: {selector}",
        browser_task_done: "Browser task completed.",
        browser_task_issues: "Browser task finished with issues.",
        browser_locate_field: "Locating field '{field}' with {selector}",
        browser_filled_field: "Filled field '{field}'.",
        browser_uploading_file: "Uploading {filename} into '{field}'.",
        browser_uploaded_file: "Uploaded file for '{field}'.",
        browser_wait_submit: "Waiting for submit control: {selector}",
        browser_submit_done: "Submit action executed.",
        browser_capture: "Captured screenshot: {filename}",
        browser_resume_uploaded: "Resume uploaded: {filename}",
        summary_none: "No run yet",
        summary_zero: "0 jobs",
        summary_jobs: "jobs",
        run_idle: "Idle",
        run_starting: "Starting",
        run_running: "Running",
        run_completed: "Completed",
        run_failed: "Failed",
        log_prepare: "Preparing workflow run.",
        log_complete: "Workflow completed.",
        log_start_failed: "Run failed to start:",
        open_job: "Open job posting",
        fit_pending: "Fit scoring pending.",
        gaps: "Gaps:",
        review: "Review:",
        status_pending: "pending",
        status_running: "running",
        status_done: "done",
        status_failed: "failed",
      },
      zh: {
        hero_badge: "可视化多智能体流程",
        hero_title: "看见每个智能体如何推进求职流程。",
        hero_subtitle: "这个界面会按步骤运行研究、匹配评分、文书生成、浏览器执行和最终审核。你可以实时看到过程，而不是只等最后一份 JSON。",
        stat_research_label: "职位来源",
        stat_research_value: "Lever + Greenhouse",
        stat_browser_label: "浏览器模式",
        stat_browser_value: "Playwright",
        stat_review_label: "审核关卡",
        stat_review_value: "人工确认",
        label_name: "姓名",
        label_experience: "工作年限",
        label_titles: "目标职位",
        label_locations: "期望地点",
        label_skills: "技能",
        label_resume_file: "简历文件",
        resume_file_note: "尚未选择文件。服务器会把上传的简历保存到 artifacts/uploads。",
        label_resume_text: "简历摘要",
        toggle_live_research: "使用实时职位源",
        toggle_allow_submit: "允许最终提交",
        toggle_visual_browser: "可视浏览器模式",
        button_run: "运行流程",
        button_reset: "重置界面",
        timeline_title: "智能体时间线",
        feed_title: "实时动态",
        browser_feed_title: "浏览器活动",
        results_title: "结果",
        empty_initial: "开始一次运行后，这里会显示职位、匹配分数、审核阻塞项和生成的申请材料。",
        empty_no_jobs: "当前筛选条件没有匹配职位。可以放宽职位名称或地点。",
        browser_no_activity: "执行期间，这里会显示浏览器动作和截图。",
        browser_session_start: "浏览器执行器以{mode}模式启动。",
        browser_session_launch_ok: "Chromium 启动成功。",
        browser_open_page: "正在打开申请页面：{url}",
        browser_wait_marker: "正在等待页面标记：{selector}",
        browser_task_done: "浏览器任务已完成。",
        browser_task_issues: "浏览器任务已结束，但存在问题。",
        browser_locate_field: "正在用 {selector} 定位字段“{field}”",
        browser_filled_field: "已填写字段“{field}”。",
        browser_uploading_file: "正在将 {filename} 上传到“{field}”。",
        browser_uploaded_file: "已完成“{field}”文件上传。",
        browser_wait_submit: "正在等待提交控件：{selector}",
        browser_submit_done: "已执行提交动作。",
        browser_capture: "已保存截图：{filename}",
        browser_resume_uploaded: "简历已上传：{filename}",
        summary_none: "尚未运行",
        summary_zero: "0 个职位",
        summary_jobs: "个职位",
        run_idle: "空闲",
        run_starting: "启动中",
        run_running: "运行中",
        run_completed: "已完成",
        run_failed: "失败",
        log_prepare: "正在准备本次流程运行。",
        log_complete: "流程已完成。",
        log_start_failed: "启动失败：",
        open_job: "打开职位链接",
        fit_pending: "匹配评分尚未完成。",
        gaps: "差距：",
        review: "审核：",
        status_pending: "待执行",
        status_running: "执行中",
        status_done: "已完成",
        status_failed: "失败",
      }
    };

    const defaultSteps = [
      { key: "research", title: "Research Agent", text: "Searches jobs, pulls descriptions, deduplicates them, and categorizes the results." },
      { key: "fit_scoring", title: "Fit Scoring Agent", text: "Scores each role, explains fit, and surfaces the biggest gaps." },
      { key: "application_writer", title: "Application Writer Agent", text: "Prepares tailored resume notes, cover letters, and Q&A scripts." },
      { key: "browser_executor", title: "Browser Executor Agent", text: "Builds browser tasks and attempts Playwright execution." },
      { key: "review_gate", title: "Review Gate", text: "Flags risky claims and enforces final user confirmation before apply." }
    ];
    const stepCopy = {
      en: defaultSteps,
      zh: [
        { key: "research", title: "研究智能体", text: "搜索职位、抓取 JD、去重并完成分类。" },
        { key: "fit_scoring", title: "匹配评分智能体", text: "为每个职位打分，解释原因，并标出主要差距。" },
        { key: "application_writer", title: "申请文书智能体", text: "生成定制化简历修改建议、求职信和问答脚本。" },
        { key: "browser_executor", title: "浏览器执行智能体", text: "构建浏览器任务并尝试使用 Playwright 执行。" },
        { key: "review_gate", title: "审核关卡", text: "标记高风险表述，并在最终申请前要求用户确认。" }
      ]
    };

    const elements = {
      body: document.body,
      steps: document.getElementById("steps"),
      feed: document.getElementById("feed"),
      jobs: document.getElementById("jobs"),
      summary: document.getElementById("summary"),
      status: document.getElementById("run-status"),
      run: document.getElementById("run"),
      reset: document.getElementById("reset"),
      browserFeed: document.getElementById("browser-feed"),
      browserShots: document.getElementById("browser-shots"),
      langEn: document.getElementById("lang-en"),
      langZh: document.getElementById("lang-zh"),
      resumeFile: document.getElementById("resume_file"),
      resumeFileNote: document.getElementById("resume-file-note"),
    };

    let state = { stepStatus: {}, result: null, runId: null, source: null, language: "en", browserEvents: [] };

    function t(key) {
      return translations[state.language][key] || translations.en[key] || key;
    }

    function formatText(key, values = {}) {
      let text = t(key);
      for (const [name, value] of Object.entries(values)) {
        text = text.replaceAll(`{${name}}`, value);
      }
      return text;
    }

    function applyLanguage() {
      document.documentElement.lang = state.language === "zh" ? "zh-CN" : "en";
      document.querySelectorAll("[data-i18n]").forEach(node => {
        node.textContent = t(node.dataset.i18n);
      });
      elements.langEn.classList.toggle("active", state.language === "en");
      elements.langZh.classList.toggle("active", state.language === "zh");
      renderSteps();
      renderJobs();
      if (!state.runId) {
        elements.status.textContent = t("run_idle");
      }
      updateResumeFileNote();
    }

    function updateResumeFileNote() {
      const file = elements.resumeFile.files && elements.resumeFile.files[0];
      elements.resumeFileNote.textContent = file ? file.name : t("resume_file_note");
    }

    function renderSteps() {
      elements.steps.innerHTML = "";
      for (const step of stepCopy[state.language]) {
        const status = state.stepStatus[step.key] || "pending";
        const card = document.createElement("div");
        card.className = "step";
        card.innerHTML = `
          <header>
            <h3>${step.title}</h3>
            <span class="status ${status}">${t(`status_${status}`)}</span>
          </header>
          <p>${step.text}</p>
        `;
        elements.steps.appendChild(card);
      }
    }

    function appendFeed(text) {
      const item = document.createElement("div");
      item.className = "feed-item";
      item.textContent = text;
      elements.feed.prepend(item);
    }

    function appendBrowserEvent(event) {
      state.browserEvents.unshift(event);
      renderBrowserActivity();
    }

    function localizedBrowserMessage(event) {
      const data = event.data || {};
      switch (event.code) {
        case "session_start":
          return formatText("browser_session_start", { mode: data.mode || "headless" });
        case "session_launch_ok":
          return t("browser_session_launch_ok");
        case "open_page":
          return formatText("browser_open_page", { url: data.url || "" });
        case "wait_marker":
          return formatText("browser_wait_marker", { selector: data.selector || "" });
        case "task_done":
          return t("browser_task_done");
        case "task_issues":
          return t("browser_task_issues");
        case "locate_field":
          return formatText("browser_locate_field", { field: data.field || "", selector: data.selector || "" });
        case "filled_field":
          return formatText("browser_filled_field", { field: data.field || "" });
        case "uploading_file":
          return formatText("browser_uploading_file", { filename: data.filename || "", field: data.field || "" });
        case "uploaded_file":
          return formatText("browser_uploaded_file", { field: data.field || "" });
        case "wait_submit":
          return formatText("browser_wait_submit", { selector: data.selector || "" });
        case "submit_done":
          return t("browser_submit_done");
        case "capture":
          return formatText("browser_capture", { filename: data.filename || "" });
        case "resume_uploaded":
          return formatText("browser_resume_uploaded", { filename: data.filename || "" });
        default:
          return event.message || "";
      }
    }

    function renderBrowserActivity() {
      if (!state.browserEvents.length) {
        elements.browserFeed.innerHTML = `<div class="empty">${t("browser_no_activity")}</div>`;
        elements.browserShots.innerHTML = "";
        return;
      }
      elements.browserFeed.innerHTML = state.browserEvents.map(event => `
        <div class="feed-item">${event.job_id ? `<strong>${event.job_id}</strong> · ` : ""}${localizedBrowserMessage(event)}</div>
      `).join("");
      const shots = state.browserEvents.filter(event => event.kind === "screenshot");
      elements.browserShots.innerHTML = shots.map(event => `
        <div class="browser-shot">
          <div>${event.job_id || ""} · ${localizedBrowserMessage(event)}</div>
          <img src="${event.path}" alt="${localizedBrowserMessage(event)}">
        </div>
      `).join("");
    }

    function renderJobs() {
      if (!state.result) {
        elements.jobs.innerHTML = `<div class="empty">${t("empty_initial")}</div>`;
        elements.summary.textContent = t("summary_none");
        return;
      }

      const jobs = state.result.research?.deduplicated_jobs || [];
      const fitByJob = Object.fromEntries((state.result.fit_scores || []).map(item => [item.job_id, item]));
      const reviewsByJob = Object.fromEntries((state.result.reviews || []).map(item => [item.job_id, item]));

      if (!jobs.length) {
        elements.jobs.innerHTML = `<div class="empty">${t("empty_no_jobs")}</div>`;
        elements.summary.textContent = t("summary_zero");
        return;
      }

      elements.summary.textContent = `${jobs.length} ${t("summary_jobs")}`;
      elements.jobs.innerHTML = jobs.map(job => {
        const fit = fitByJob[job.id];
        const review = reviewsByJob[job.id];
        const pills = [];
        if (job.category) pills.push(`<span class="pill">${job.category}</span>`);
        if (fit) pills.push(`<span class="pill">fit ${fit.score}/100</span>`);
        if (review) pills.push(`<span class="pill">${review.status}</span>`);
        const gaps = fit?.gaps?.length ? `<div><strong>${t("gaps")}</strong> ${fit.gaps.join(", ")}</div>` : "";
        const notes = review?.notes?.length ? `<div><strong>${t("review")}</strong> ${review.notes.join(" | ")}</div>` : "";
        return `
          <article class="job-card">
            <h3>${job.title}</h3>
            <div class="meta">${job.company} · ${job.location} · ${job.source}</div>
            <div class="pill-row">${pills.join("")}</div>
            <div>${fit?.rationale || t("fit_pending")}</div>
            ${gaps}
            ${notes}
            <div style="margin-top:10px;"><a href="${job.url}" target="_blank" rel="noreferrer">${t("open_job")}</a></div>
          </article>
        `;
      }).join("");
    }

    function resetView() {
      const language = state.language || "en";
      state = { stepStatus: {}, result: null, runId: null, source: null, language, browserEvents: [] };
      elements.feed.innerHTML = "";
      elements.status.textContent = t("run_idle");
      renderSteps();
      renderJobs();
      renderBrowserActivity();
    }

    async function startRun() {
      resetView();
      elements.run.disabled = true;
      elements.status.textContent = t("run_starting");
      appendFeed(t("log_prepare"));

      let uploadedResumePath = "";
      const file = elements.resumeFile.files && elements.resumeFile.files[0];
      if (file) {
        const formData = new FormData();
        formData.append("resume", file);
        const uploadResponse = await fetch("/api/uploads", {
          method: "POST",
          body: formData
        });
        const uploadData = await uploadResponse.json();
        uploadedResumePath = uploadData.path || "";
        appendBrowserEvent({
          kind: "task",
          code: "resume_uploaded",
          data: { filename: uploadData.filename || "" },
          message: `Resume uploaded: ${uploadData.filename}`
        });
      }

      const payload = {
        candidate: {
          name: document.getElementById("name").value.trim(),
          target_titles: document.getElementById("titles").value.split(",").map(v => v.trim()).filter(Boolean),
          preferred_locations: document.getElementById("locations").value.split(",").map(v => v.trim()).filter(Boolean),
          skills: document.getElementById("skills").value.split(",").map(v => v.trim()).filter(Boolean),
          years_experience: Number(document.getElementById("experience").value || "0"),
          resume_text: document.getElementById("resume_text").value.trim(),
          resume_path: uploadedResumePath,
        },
        live_research: document.getElementById("live_research").checked,
        allow_submit: document.getElementById("allow_submit").checked,
        visual_browser: document.getElementById("visual_browser").checked
      };

      const response = await fetch("/api/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await response.json();
      state.runId = data.run_id;
      elements.status.textContent = t("run_running");
      connectEvents();
    }

    function connectEvents() {
      state.source = new EventSource(`/api/runs/${state.runId}/events`);
      state.source.onmessage = event => {
        const data = JSON.parse(event.data);
        if (data.type === "step") {
          state.stepStatus[data.step] = data.status;
          if (data.message) appendFeed(data.message);
          renderSteps();
        } else if (data.type === "result") {
          state.result = data.payload;
          appendFeed(t("log_complete"));
          elements.status.textContent = t("run_completed");
          renderJobs();
        } else if (data.type === "error") {
          appendFeed(data.message);
          elements.status.textContent = t("run_failed");
        } else if (data.type === "browser") {
          appendBrowserEvent(data.payload);
        } else if (data.type === "done") {
          elements.run.disabled = false;
          if (state.source) state.source.close();
        } else if (data.type === "log") {
          appendFeed(data.message);
        }
      };
      state.source.onerror = () => {
        elements.run.disabled = false;
      };
    }

    elements.run.addEventListener("click", () => {
      startRun().catch(error => {
        appendFeed(`${t("log_start_failed")} ${error}`);
        elements.run.disabled = false;
        elements.status.textContent = t("run_failed");
      });
    });
    elements.langEn.addEventListener("click", () => {
      state.language = "en";
      applyLanguage();
    });
    elements.langZh.addEventListener("click", () => {
      state.language = "zh";
      applyLanguage();
    });
    elements.resumeFile.addEventListener("change", updateResumeFileNote);
    elements.reset.addEventListener("click", resetView);
    applyLanguage();
    renderBrowserActivity();
  </script>
</body>
</html>
"""


class RunStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._runs: dict[str, dict] = {}

    def create_run(self, payload: dict) -> str:
        run_id = uuid.uuid4().hex
        with self._lock:
            self._runs[run_id] = {
                "status": "running",
                "events": [],
                "queues": [],
                "result": None,
                "payload": payload,
            }
        return run_id

    def emit(self, run_id: str, event: dict) -> None:
        with self._lock:
            run = self._runs[run_id]
            run["events"].append(event)
            queues = list(run["queues"])
        for queue in queues:
            queue.put(event)

    def finish(self, run_id: str, result: dict) -> None:
        with self._lock:
            run = self._runs[run_id]
            run["status"] = "done"
            run["result"] = result
        self.emit(run_id, {"type": "result", "payload": result})
        self.emit(run_id, {"type": "done"})

    def fail(self, run_id: str, message: str) -> None:
        with self._lock:
            self._runs[run_id]["status"] = "failed"
        self.emit(run_id, {"type": "error", "message": message})
        self.emit(run_id, {"type": "done"})

    def subscribe(self, run_id: str) -> Queue:
        queue: Queue = Queue()
        with self._lock:
            run = self._runs[run_id]
            run["queues"].append(queue)
            history = list(run["events"])
        for event in history:
            queue.put(event)
        return queue

    def unsubscribe(self, run_id: str, queue: Queue) -> None:
        with self._lock:
            run = self._runs.get(run_id)
            if not run:
                return
            if queue in run["queues"]:
                run["queues"].remove(queue)


class WorkflowRunner:
    def __init__(self, store: RunStore) -> None:
        self.store = store

    def start(self, payload: dict) -> str:
        run_id = self.store.create_run(payload)
        thread = threading.Thread(target=self._run, args=(run_id, payload), daemon=True)
        thread.start()
        return run_id

    def _run(self, run_id: str, payload: dict) -> None:
        try:
            candidate = self._build_candidate(payload.get("candidate") or {})
            live_research = bool(payload.get("live_research", True))
            allow_submit = bool(payload.get("allow_submit", False))
            visual_browser = bool(payload.get("visual_browser", False))
            top_n = int(payload.get("top_n", 3))

            browser_agent = BrowserExecutorAgent(
                headless=not visual_browser,
                event_sink=lambda event: self.store.emit(run_id, {"type": "browser", "payload": event}),
            )
            system = JobMatchSystem(browser_agent=browser_agent)
            config = WorkflowConfig(
                top_n_applications=top_n,
                allow_submit=allow_submit,
                live_research=live_research,
                research_sources=sample_research_sources(),
            )
            jobs = [] if live_research else sample_jobs()

            self.store.emit(run_id, {"type": "log", "message": "Candidate profile loaded."})
            self.store.emit(run_id, {"type": "step", "step": "research", "status": "running", "message": "Research agent is collecting jobs."})
            research = system.research_agent.run(
                jobs=jobs,
                candidate=candidate,
                sources=config.research_sources if config.live_research else None,
            ).payload
            self.store.emit(
                run_id,
                {
                    "type": "step",
                    "step": "research",
                    "status": "done",
                    "message": f"Research found {len(research.discovered_jobs)} jobs and kept {len(research.deduplicated_jobs)} unique matches.",
                },
            )

            self.store.emit(run_id, {"type": "step", "step": "fit_scoring", "status": "running", "message": "Fit scoring agent is ranking the matches."})
            fit_scores = system.fit_agent.run(candidate, research.deduplicated_jobs).payload
            self.store.emit(
                run_id,
                {
                    "type": "step",
                    "step": "fit_scoring",
                    "status": "done",
                    "message": f"Fit scoring completed for {len(fit_scores)} jobs.",
                },
            )

            self.store.emit(run_id, {"type": "step", "step": "application_writer", "status": "running", "message": "Application writer is drafting materials."})
            applications = system.writer_agent.run(
                candidate,
                research.deduplicated_jobs,
                fit_scores,
                top_n=config.top_n_applications,
            ).payload
            self.store.emit(
                run_id,
                {
                    "type": "step",
                    "step": "application_writer",
                    "status": "done",
                    "message": f"Generated {len(applications)} application packages.",
                },
            )

            job_lookup = {job.id: job for job in research.deduplicated_jobs}
            browser_tasks = [
                system.browser_task_builder.build(candidate, job_lookup[application.job_id], application)
                for application in applications
            ]
            self.store.emit(run_id, {"type": "step", "step": "browser_executor", "status": "running", "message": "Browser executor is building and running Playwright tasks."})
            browser_results = system.browser_agent.run(browser_tasks, submit=config.allow_submit).payload
            self.store.emit(
                run_id,
                {
                    "type": "step",
                    "step": "browser_executor",
                    "status": "done",
                    "message": f"Browser executor returned {len(browser_results)} task results.",
                },
            )

            self.store.emit(run_id, {"type": "step", "step": "review_gate", "status": "running", "message": "Review gate is checking for risky claims and blockers."})
            reviews = system.review_agent.run(applications, fit_scores, browser_results).payload
            self.store.emit(
                run_id,
                {
                    "type": "step",
                    "step": "review_gate",
                    "status": "done",
                    "message": "Review gate finished. Final user confirmation is still required before any real apply.",
                },
            )

            result = {
                "research": asdict(research),
                "fit_scores": [asdict(item) for item in fit_scores],
                "application_packages": [asdict(item) for item in applications],
                "browser_results": [asdict(item) for item in browser_results],
                "reviews": [asdict(item) for item in reviews],
            }
            self.store.finish(run_id, result)
        except Exception as exc:  # pragma: no cover
            self.store.fail(run_id, f"Workflow failed: {exc}")

    def _build_candidate(self, data: dict) -> CandidateProfile:
        base = sample_candidate()
        resume_path = data.get("resume_path")
        return CandidateProfile(
            name=data.get("name") or base.name,
            target_titles=data.get("target_titles") or base.target_titles,
            preferred_locations=data.get("preferred_locations") or base.preferred_locations,
            skills=data.get("skills") or base.skills,
            years_experience=int(data.get("years_experience") or base.years_experience),
            resume_text=data.get("resume_text") or base.resume_text,
            resume_path=resume_path if resume_path else None,
            achievements=base.achievements,
        )


class AppHandler(BaseHTTPRequestHandler):
    store = RunStore()
    runner = WorkflowRunner(store)
    upload_dir = Path("artifacts/uploads")

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._html(INDEX_HTML)
            return
        if parsed.path.startswith("/artifacts/"):
            self._file(parsed.path.lstrip("/"))
            return
        if parsed.path.startswith("/api/runs/") and parsed.path.endswith("/events"):
            run_id = parsed.path.split("/")[3]
            self._stream_events(run_id)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/api/uploads":
            try:
                payload = self._handle_upload()
            except ValueError as exc:
                self._json({"error": str(exc)}, status=HTTPStatus.BAD_REQUEST)
                return
            self._json(payload, status=HTTPStatus.CREATED)
            return
        if parsed.path == "/api/runs":
            payload = self._json_body()
            run_id = self.runner.start(payload)
            self._json({"run_id": run_id}, status=HTTPStatus.ACCEPTED)
            return
        self.send_error(HTTPStatus.NOT_FOUND)

    def _json_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        return json.loads(raw.decode("utf-8"))

    def _handle_upload(self) -> dict:
        content_type = self.headers.get("Content-Type", "")
        boundary_match = content_type.split("boundary=", 1)
        if "multipart/form-data" not in content_type or len(boundary_match) != 2:
            raise ValueError("Expected multipart/form-data upload.")

        boundary = boundary_match[1].encode("utf-8")
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        parts = raw.split(b"--" + boundary)

        file_name = None
        file_bytes = None
        for part in parts:
            if b'name="resume"' not in part:
                continue
            header_blob, _, body = part.partition(b"\r\n\r\n")
            disposition = header_blob.decode("utf-8", errors="ignore")
            name_match = None
            if 'filename="' in disposition:
                name_match = disposition.split('filename="', 1)[1].split('"', 1)[0]
            if not name_match:
                continue
            file_name = os.path.basename(name_match)
            file_bytes = body.rstrip(b"\r\n-")
            break

        if not file_name or file_bytes is None:
            raise ValueError("Resume file was not provided.")

        self.upload_dir.mkdir(parents=True, exist_ok=True)
        safe_name = f"{uuid.uuid4().hex}-{file_name}"
        target = self.upload_dir / safe_name
        target.write_bytes(file_bytes)
        return {"filename": file_name, "path": str(target.resolve())}

    def _json(self, payload: dict, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _html(self, html: str) -> None:
        body = html.encode("utf-8")
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _file(self, relative_path: str) -> None:
        root = Path.cwd().resolve()
        target = (root / relative_path).resolve()
        artifacts_root = (root / "artifacts").resolve()
        if artifacts_root not in target.parents and target != artifacts_root:
            self.send_error(HTTPStatus.FORBIDDEN)
            return
        if not target.exists() or not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        content_type = "application/octet-stream"
        if target.suffix.lower() == ".png":
            content_type = "image/png"
        elif target.suffix.lower() in {".jpg", ".jpeg"}:
            content_type = "image/jpeg"
        elif target.suffix.lower() == ".txt":
            content_type = "text/plain; charset=utf-8"
        body = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _stream_events(self, run_id: str) -> None:
        queue = self.store.subscribe(run_id)
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            while True:
                try:
                    event = queue.get(timeout=20)
                except Empty:
                    event = {"type": "log", "message": f"Heartbeat {int(time.time())}"}
                self.wfile.write(f"data: {json.dumps(event)}\n\n".encode("utf-8"))
                self.wfile.flush()
                if event.get("type") == "done":
                    break
        except BrokenPipeError:
            pass
        finally:
            self.store.unsubscribe(run_id, queue)

    def log_message(self, format: str, *args) -> None:
        return


def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Find Your Job UI running at http://{host}:{port}")
    server.serve_forever()
