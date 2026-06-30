#!/usr/bin/env python3
"""
SafeFall Active Learning Wizard — Gradio UI (legacy fallback).

Uses the framework-agnostic ActiveLearningWizard from wizard.py and wraps
it with a Gradio desktop interface.
"""

from typing import Dict

try:
    import gradio as gr
    HAS_GRADIO = True
except ImportError:
    HAS_GRADIO = False
    print("Gradio not installed. Please run: pip install gradio")

from wizard import ActiveLearningWizard
from utils import CameraCapture


def _initialize_streaming(self):
    """
    Initialize all components and yield (status_text, health_html) after
    each stage so the UI updates progressively rather than all at once.
    Used exclusively by the Gradio demo.load event.
    """
    # Pose estimator
    if self.pose_estimator.initialize():
        self._component_health["pose_estimator"] = "ready"
        status = "Pose estimator ready"
    else:
        self._component_health["pose_estimator"] = "placeholder"
        status = "Pose estimator failed (placeholder mode)"
    yield status, _build_health_html(self._component_health)

    # Fall detector
    if self.sia_detector.initialize():
        self._component_health["fall_detector"] = (
            "ready" if self.sia_detector.model is not None else "placeholder"
        )
        status = "Fall detector ready"
    else:
        self._component_health["fall_detector"] = "placeholder"
        status = "Fall detector failed (placeholder mode)"
    yield status, _build_health_html(self._component_health)

    # Feedback generator
    if self.feedback_generator.initialize():
        self._component_health["feedback_generator"] = "ready"
        status = "Feedback generator ready"
    else:
        self._component_health["feedback_generator"] = "error"
        status = "Feedback generator failed"
    yield status, _build_health_html(self._component_health)

    # WebSocket server
    if self.ws_server.start():
        self._component_health["websocket"] = "ready"
        status = "WebSocket server started on port 8765"
    else:
        self._component_health["websocket"] = "error"
        status = f"WebSocket server FAILED: {self.ws_server._start_error or 'unknown'}"
    yield status, _build_health_html(self._component_health)

    # Camera health derived from actual camera state
    self._component_health["camera"] = self._get_camera_health()
    self._initialized = True
    yield "System ready", _build_health_html(self._component_health)


# Attach the Gradio-specific streaming initializer to the wizard class
ActiveLearningWizard.initialize_streaming = _initialize_streaming


# ═══════════════════════════════════════════════════════════════
# Gradio UI — broken into composable builder functions
# ═══════════════════════════════════════════════════════════════

def _build_theme_and_css():
    """Return (theme, css_string) for the Gradio app."""
    safefall_theme = gr.themes.Base(
        primary_hue="blue",
        secondary_hue="slate",
        neutral_hue="slate",
        font=gr.themes.GoogleFont("Inter"),
        text_size=gr.themes.sizes.text_md,
    ).set(
        body_background_fill="#0F172A",
        block_background_fill="#1E293B",
        block_border_color="#334155",
        body_text_color="#F1F5F9",
        block_title_text_color="#F1F5F9",
        block_label_text_color="#CBD5E1",
        input_background_fill="#0F172A",
        button_primary_background_fill="#2563EB",
        button_primary_text_color="#FFFFFF",
        button_secondary_background_fill="#334155",
        button_secondary_text_color="#F1F5F9",
        button_cancel_background_fill="#DC2626",
        button_cancel_text_color="#FFFFFF",
        block_shadow="none",
        container_radius="12px",
    )

    custom_css = """
    /* ── Base dark background ─────────────────────────────────── */
    body, .gradio-container, html {
        background-color: #0F172A !important;
        color: #F1F5F9 !important;
    }

    /* ── All text nodes ──────────────────────────────────────── */
    .gradio-container *,
    .gradio-container label,
    .gradio-container span,
    .gradio-container p,
    .gradio-container div,
    .gradio-container h1,
    .gradio-container h2,
    .gradio-container h3,
    .gradio-container h4,
    .gradio-container li {
        color: #F1F5F9 !important;
    }

    /* ── Cards / blocks ──────────────────────────────────────── */
    .gradio-container .form {
        background-color: #1E293B !important;
        border: 1px solid #334155 !important;
        border-radius: 12px !important;
    }

    /* ── Inputs & textareas ──────────────────────────────────── */
    .gradio-container textarea,
    .gradio-container input[type="text"] {
        background-color: #0F172A !important;
        color: #F1F5F9 !important;
        border: 1px solid #475569 !important;
        border-radius: 8px !important;
    }
    .gradio-container textarea::placeholder,
    .gradio-container input::placeholder {
        color: #64748B !important;
    }

    /* ── Accordion ───────────────────────────────────────────── */
    .gradio-container .accordion > .label-wrap,
    .gradio-container .accordion button,
    .gradio-container details summary {
        background-color: #1E293B !important;
        color: #F1F5F9 !important;
        border: 1px solid #334155 !important;
        border-radius: 8px !important;
    }
    .gradio-container .accordion .inner {
        background-color: #162032 !important;
        border: 1px solid #334155 !important;
    }

    /* ── Markdown / prose ────────────────────────────────────── */
    .gradio-container .prose,
    .gradio-container .markdown-body,
    .gradio-container .prose *,
    .gradio-container .markdown-body * {
        color: #E2E8F0 !important;
    }
    .gradio-container .prose strong,
    .gradio-container .markdown-body strong {
        color: #F1F5F9 !important;
    }

    /* ── Feedback banner ─────────────────────────────────────── */
    .feedback-banner {
        font-size: 26px !important;
        font-weight: 700 !important;
        padding: 22px 28px !important;
        border-radius: 12px !important;
        text-align: center !important;
        margin: 14px 0 !important;
        line-height: 1.4 !important;
    }
    .feedback-success {
        background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
        color: #ECFDF5 !important;
        border: 2px solid #10B981 !important;
    }
    .feedback-warning {
        background: linear-gradient(135deg, #D97706 0%, #B45309 100%) !important;
        color: #FFFBEB !important;
        border: 2px solid #F59E0B !important;
    }
    .feedback-error {
        background: linear-gradient(135deg, #DC2626 0%, #B91C1C 100%) !important;
        color: #FEF2F2 !important;
        border: 2px solid #EF4444 !important;
    }
    .feedback-neutral {
        background: linear-gradient(135deg, #1D4ED8 0%, #1E40AF 100%) !important;
        color: #EFF6FF !important;
        border: 2px solid #3B82F6 !important;
    }

    /* ── Session stats ────────────────────────────────────────── */
    .session-timer {
        font-size: 36px !important;
        font-weight: 800 !important;
        text-align: center !important;
        color: #F1F5F9 !important;
        padding: 16px !important;
        background: #1E293B !important;
        border-radius: 12px !important;
        border: 2px solid #334155 !important;
        letter-spacing: 2px !important;
    }
    .fall-count {
        font-size: 28px !important;
        font-weight: 700 !important;
        text-align: center !important;
        color: #F1F5F9 !important;
        padding: 16px !important;
        background: #1E293B !important;
        border-radius: 12px !important;
        border: 2px solid #334155 !important;
    }

    /* ── Feedback history ────────────────────────────────────── */
    .feedback-history {
        max-height: 400px !important;
        overflow-y: auto !important;
        font-size: 14px !important;
        line-height: 1.7 !important;
    }
    .feedback-history::-webkit-scrollbar { width: 6px; }
    .feedback-history::-webkit-scrollbar-track { background: #1E293B; }
    .feedback-history::-webkit-scrollbar-thumb { background: #475569; border-radius: 3px; }

    /* ── QR code area ────────────────────────────────────────── */
    .qr-container {
        text-align: center !important;
        padding: 20px !important;
        background: #1E293B !important;
        border-radius: 12px !important;
        border: 2px solid #334155 !important;
    }

    /* ── Header ──────────────────────────────────────────────── */
    .header-title {
        font-size: 26px !important;
        font-weight: 800 !important;
        color: #F1F5F9 !important;
        margin-bottom: 4px !important;
        letter-spacing: -0.5px !important;
    }

    /* ── Connection status badge ─────────────────────────────── */
    .connection-status {
        font-size: 14px !important;
        font-weight: 600 !important;
        padding: 6px 14px !important;
        border-radius: 20px !important;
        display: inline-block !important;
        letter-spacing: 0.3px !important;
    }
    .status-connected {
        background: #064E3B !important;
        color: #6EE7B7 !important;
        border: 1px solid #10B981 !important;
    }
    .status-disconnected {
        background: #1C1917 !important;
        color: #94A3B8 !important;
        border: 1px solid #475569 !important;
    }

    /* ── Divider ─────────────────────────────────────────────── */
    hr.sf-divider {
        margin: 14px 0 !important;
        border: none !important;
        border-top: 1px solid #334155 !important;
    }

    /* ── Tab / section labels ────────────────────────────────── */
    .gradio-container .tabitem,
    .gradio-container .selected {
        background-color: #1E293B !important;
    }

    /* ── Health status indicators ─────────────────────────────── */
    .health-ready { color: #34D399 !important; }
    .health-placeholder { color: #FBBF24 !important; }
    .health-error { color: #F87171 !important; }
    """

    return safefall_theme, custom_css


def _build_health_html(component_health: Dict[str, str]) -> str:
    """Render component health as HTML."""
    status_map = {
        "ready": ("Ready", "#34D399", "●"),
        "idle": ("Idle", "#94A3B8", "○"),
        "placeholder": ("Placeholder", "#FBBF24", "△"),
        "not_initialized": ("Not initialized", "#94A3B8", "○"),
        "disconnected": ("Disconnected", "#F87171", "✕"),
    }
    rows = ""
    for comp, status in component_health.items():
        display_name = comp.replace("_", " ").title()
        if status.startswith("error"):
            color, icon, label = "#F87171", "✕", status
        else:
            label, color, icon = status_map.get(
                status, (status, "#94A3B8", "?")
            )
        rows += (
            f'<div style="display:flex;justify-content:space-between;'
            f'padding:4px 0;border-bottom:1px solid #1E293B;">'
            f'<span style="color:#CBD5E1;font-size:13px;">{display_name}</span>'
            f'<span style="color:{color};font-weight:600;font-size:13px;">'
            f'{icon} {label}</span></div>'
        )
    return (
        f'<div style="padding:8px;background:#0F172A;border-radius:8px;'
        f'border:1px solid #334155;">{rows}</div>'
    )


def create_gradio_interface(wizard: ActiveLearningWizard) -> gr.Blocks:
    """Create the Gradio interface for the wizard."""
    safefall_theme, custom_css = _build_theme_and_css()

    with gr.Blocks(
        title="SafeFall Active Learning Wizard",
        theme=safefall_theme,
        css=custom_css,
        js="() => {document.body.classList.add('dark')}",
    ) as demo:
        # ── Header ──
        with gr.Row():
            with gr.Column(scale=1):
                gr.HTML("""
                <div style="display: flex; align-items: center; gap: 16px;">
                    <div>
                        <div class="header-title">SafeFall Active Learning Wizard</div>
                        <div style="color: #94A3B8; font-size: 14px; font-weight: 500;">Real-time Fall Technique Training</div>
                    </div>
                </div>
                """)
            with gr.Column(scale=1):
                connection_status = gr.HTML("""
                <div style="text-align: right;">
                    <span class="connection-status status-disconnected">● No Connection</span>
                </div>
                """)

        gr.HTML("<hr class='sf-divider'>")

        # ── Main content ──
        with gr.Row():
            # Left: Video feed (60%)
            with gr.Column(scale=6):
                video_output = gr.Image(
                    label="Camera Feed", type="numpy", height=480
                )

                feedback_banner = gr.HTML("""
                <div class="feedback-banner feedback-neutral">
                    <strong>Ready to start your training session</strong>
                </div>
                """)

                with gr.Row():
                    with gr.Column(scale=1):
                        session_timer_display = gr.HTML("""
                        <div class="session-timer">00:00</div>
                        <div style="text-align: center; color: #94A3B8; font-size: 13px; font-weight: 600; margin-top: 6px; letter-spacing: 0.5px; text-transform: uppercase;">Session Time</div>
                        """)
                    with gr.Column(scale=1):
                        fall_count_display = gr.HTML("""
                        <div class="fall-count">Falls: 0</div>
                        <div style="text-align: center; color: #94A3B8; font-size: 13px; font-weight: 600; margin-top: 6px; letter-spacing: 0.5px; text-transform: uppercase;">Practice Count</div>
                        """)

                with gr.Row():
                    available_cams = CameraCapture.list_cameras()
                    cam_choices = [f"Camera {i}" for i in available_cams] or ["Camera 0"]
                    camera_dropdown = gr.Dropdown(
                        choices=cam_choices, value=cam_choices[0],
                        label="Camera", scale=1,
                    )
                    study_id_input = gr.Textbox(
                        label="Study ID",
                        placeholder="e.g. P001",
                        scale=1,
                        info="Required for data export (letters, numbers, dash, underscore)",
                    )
                    start_btn = gr.Button(
                        "▶ START SESSION", variant="primary", size="lg", scale=2,
                    )
                    pause_btn = gr.Button(
                        "⏸ PAUSE", variant="secondary", size="lg",
                        scale=1, visible=False,
                    )
                    stop_btn = gr.Button(
                        "⏹ END SESSION", variant="stop", size="lg",
                        scale=1, visible=False,
                    )

            # Right: Connection panel + info (40%)
            with gr.Column(scale=4):
                with gr.Column(visible=True) as connection_panel:
                    gr.Markdown("### Connect Your Device")
                    qr_output = gr.Image(
                        label="", type="pil", height=300,
                        show_label=False, container=False,
                        elem_classes="qr-container",
                    )
                    session_code_display = gr.Markdown(
                        "**Session Code:** Not started",
                        elem_classes="session-code",
                    )
                    gr.HTML("""
                    <div style="background:#0F172A; border-radius:8px; padding:14px; border:1px solid #334155; margin-top:8px;">
                        <div style="color:#CBD5E1; font-size:13px; font-weight:700; margin-bottom:8px; text-transform:uppercase; letter-spacing:0.5px;">Instructions</div>
                        <ol style="margin:0; padding-left:18px; color:#E2E8F0; font-size:14px; line-height:2;">
                            <li>Open SafeFall Coach app</li>
                            <li>Go to Active Learning</li>
                            <li>Tap "Connect to Desktop"</li>
                            <li>Scan the QR code above</li>
                        </ol>
                    </div>
                    """)

                # System Health (collapsible)
                with gr.Accordion("System Health", open=False):
                    health_display = gr.HTML(
                        _build_health_html(wizard._component_health)
                    )

                # Developer info (collapsible)
                with gr.Accordion("Developer Info", open=False):
                    pose_info = gr.Textbox(
                        label="Pose Analysis", lines=10,
                        max_lines=15, interactive=False,
                    )

                # Feedback history
                gr.HTML("""
                <div style="color:#F1F5F9; font-size:14px; font-weight:700; margin: 12px 0 6px; text-transform:uppercase; letter-spacing:0.5px;">Feedback History</div>
                """)
                feedback_log = gr.HTML("""
                <div class="feedback-history" style="padding: 12px; background: #0F172A; border-radius: 8px; border: 1px solid #334155;">
                    <div style="color: #64748B; font-style: italic;">No feedback yet — start a session to begin</div>
                </div>
                """)

                # Export info (shown after session ends)
                export_info = gr.HTML("")

                # Export / discard buttons (shown after session ends)
                with gr.Row():
                    export_data_btn = gr.Button(
                        "💾 Export Session Data", variant="primary",
                        visible=False, size="sm",
                    )
                    discard_data_btn = gr.Button(
                        "🗑 Discard Data", variant="secondary",
                        visible=False, size="sm",
                    )

        # Hidden status output
        status_output = gr.Textbox(label="System Status", visible=False)

        # ── Shared feedback state ──
        feedback_state = {
            "last_msg": "",
            "feedback_list": [],
            "start_time": None,
            "current_severity": "neutral",
        }

        # ── Event handlers ──

        def on_start(study_id_val):
            """Start session handler."""
            # Validate study ID format (optional — defaults to 'anonymous')
            study_id_val = (study_id_val or "").strip()
            if study_id_val and not re.match(r'^[A-Za-z0-9_-]+$', study_id_val):
                raise gr.Error(
                    "Study ID must contain only letters, numbers, dashes, "
                    "and underscores."
                )

            # Reset feedback state
            feedback_state["last_msg"] = ""
            feedback_state["feedback_list"] = []
            feedback_state["start_time"] = None
            feedback_state["current_severity"] = "neutral"

            qr, info, status = wizard.start_session(study_id=study_id_val)

            connection_html = """
            <div style="text-align: right;">
                <span class="connection-status status-connected">● Session Active</span>
            </div>
            """

            session_id = "unknown"
            if "Session ID:" in info:
                for line in info.strip().split("\n"):
                    if "Session ID:" in line:
                        session_id = line.split("Session ID:")[-1].strip()
                        break

            session_code_md = f"**Session Code:** `{session_id}`"

            reset_feedback_log = """
            <div class="feedback-history" style="padding: 12px; background: #0F172A; border-radius: 8px; border: 1px solid #334155;">
                <div style="color: #64748B; font-style: italic;">No feedback yet — session just started</div>
            </div>
            """
            reset_fall_count = """
            <div class="fall-count">Falls: 0</div>
            <div style="text-align: center; color: #94A3B8; font-size: 13px; font-weight: 600; margin-top: 6px; letter-spacing: 0.5px; text-transform: uppercase;">Practice Count</div>
            """
            reset_timer = """
            <div class="session-timer">00:00</div>
            <div style="text-align: center; color: #94A3B8; font-size: 13px; font-weight: 600; margin-top: 6px; letter-spacing: 0.5px; text-transform: uppercase;">Session Time</div>
            """
            reset_banner = """
            <div class="feedback-banner feedback-neutral">
                <strong>Session started — begin your practice!</strong>
            </div>
            """

            return (
                qr,
                session_code_md,
                connection_html,
                gr.update(visible=False),   # Hide start
                gr.update(visible=True),    # Show pause
                gr.update(visible=True),    # Show stop
                status,
                "",  # Clear export info
                reset_feedback_log,
                reset_fall_count,
                reset_timer,
                reset_banner,
                _build_health_html(wizard._component_health),  # Reflect camera=ready immediately
                gr.update(visible=False),   # Hide export btn
                gr.update(visible=False),   # Hide discard btn
            )

        def on_pause():
            """Toggle pause."""
            is_paused = wizard.toggle_pause()
            label = "▶ RESUME" if is_paused else "⏸ PAUSE"
            return gr.update(value=label)

        def on_stop():
            """Stop session handler."""
            summary, has_data = wizard.stop_session()

            connection_html = """
            <div style="text-align: right;">
                <span class="connection-status status-disconnected">● Session Ended</span>
            </div>
            """

            feedback_html = f"""
            <div class="feedback-banner feedback-neutral">
                <strong>Session Complete!</strong><br>
                <div style="font-size: 16px; margin-top: 10px; opacity: 0.9;">{summary.replace(chr(10), '<br>')}</div>
            </div>
            """

            prompt_html = (
                '<div style="background:#0F172A;border-radius:8px;padding:14px;'
                'border:1px solid #334155;margin-top:8px;">'
                '<div style="color:#F1F5F9;font-weight:700;font-size:14px;'
                'margin-bottom:6px;">Session data collected.</div>'
                '<div style="color:#94A3B8;font-size:13px;">Would you like to export '
                'the data to disk or discard it?</div>'
                '</div>'
            ) if has_data else ""

            return (
                None,
                feedback_html,
                connection_html,
                gr.update(visible=True),    # Show start
                gr.update(visible=False),   # Hide pause
                gr.update(visible=False),   # Hide stop
                "Session stopped",
                prompt_html,
                _build_health_html(wizard._component_health),
                gr.update(visible=has_data),   # Show export btn
                gr.update(visible=has_data),   # Show discard btn
            )

        def on_export_data():
            """Export collected session data to disk."""
            export_paths = wizard.export_pending_data()
            if not export_paths:
                export_html = (
                    '<div style="background:#0F172A;border-radius:8px;padding:14px;'
                    'border:1px solid #334155;margin-top:8px;">'
                    '<div style="color:#FBBF24;font-size:13px;">No data to export.</div>'
                    '</div>'
                )
            else:
                export_html = (
                    '<div style="background:#0F172A;border-radius:8px;padding:14px;'
                    'border:1px solid #334155;margin-top:8px;">'
                    '<div style="color:#34D399;font-weight:700;font-size:14px;'
                    'margin-bottom:8px;">✓ Data Exported Successfully</div>'
                )
                for label, path in export_paths.items():
                    export_html += (
                        f'<div style="color:#CBD5E1;font-size:12px;margin-bottom:4px;">'
                        f'<strong>{label}:</strong> {path}</div>'
                    )
                export_html += '</div>'
            return (
                export_html,
                gr.update(visible=False),
                gr.update(visible=False),
            )

        def on_discard_data():
            """Discard collected session data."""
            wizard.discard_pending_data()
            discard_html = (
                '<div style="background:#0F172A;border-radius:8px;padding:14px;'
                'border:1px solid #334155;margin-top:8px;">'
                '<div style="color:#94A3B8;font-size:13px;">Session data discarded.</div>'
                '</div>'
            )
            return (
                discard_html,
                gr.update(visible=False),
                gr.update(visible=False),
            )

        def update_stream():
            """Single generator for video + UI updates (~30fps)."""
            if feedback_state["start_time"] is None:
                feedback_state["start_time"] = time.time()

            ui_tick = 0

            while wizard._processing:
                annotated, pose, feedback_msg = wizard.process_and_get_frame()

                ui_tick += 1
                if ui_tick % 3 == 0:
                    feedback_html = gr.update()
                    history_html = gr.update()
                    health_html = gr.update()

                    if feedback_msg and feedback_msg != feedback_state["last_msg"]:
                        feedback_state["last_msg"] = feedback_msg

                        severity = "neutral"
                        upper = feedback_msg.upper()
                        if "FALL DETECTED" in upper:
                            severity = "error"
                        elif "GOOD" in upper or "GREAT" in upper:
                            severity = "success"
                        elif "WARNING" in upper or "NEEDS" in upper:
                            severity = "warning"

                        feedback_state["current_severity"] = severity
                        feedback_html = f"""
                        <div class="feedback-banner feedback-{severity}">
                            <strong>{feedback_msg}</strong>
                        </div>
                        """

                        timestamp = time.strftime("%H:%M:%S")
                        feedback_state["feedback_list"].insert(0, {
                            "time": timestamp,
                            "message": feedback_msg,
                            "severity": severity,
                        })
                        feedback_state["feedback_list"] = feedback_state["feedback_list"][:10]

                        history_html = '<div class="feedback-history" style="padding: 12px; background: #0F172A; border-radius: 8px; border: 1px solid #334155;">'
                        for item in feedback_state["feedback_list"]:
                            sev_icon = {"success": "✓", "warning": "⚠", "error": "✕", "neutral": "ℹ"}.get(item["severity"], "•")
                            sev_color = {"success": "#34D399", "warning": "#FBBF24", "error": "#F87171", "neutral": "#60A5FA"}.get(item["severity"], "#94A3B8")
                            history_html += f"""
                            <div style="margin-bottom: 10px; padding-bottom: 10px; border-bottom: 1px solid #1E293B;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                    <span style="color: {sev_color}; font-weight: 700; font-size: 15px;">{sev_icon}</span>
                                    <span style="color: #64748B; font-size: 11px; font-weight: 500;">{item["time"]}</span>
                                </div>
                                <div style="color: #E2E8F0; font-size: 13px; line-height: 1.5;">{item["message"]}</div>
                            </div>
                            """
                        history_html += '</div>'

                    # Timer + fall count from framework-agnostic state
                    ui_state = wizard.get_session_ui_state()

                    timer_html = f"""
                    <div class="session-timer">{ui_state["duration_str"]}</div>
                    <div style="text-align: center; color: #94A3B8; font-size: 13px; font-weight: 600; margin-top: 6px; letter-spacing: 0.5px; text-transform: uppercase;">Session Time</div>
                    """

                    fall_html = f"""
                    <div class="fall-count">Falls: {ui_state["fall_count"]}</div>
                    <div style="text-align: center; color: #94A3B8; font-size: 13px; font-weight: 600; margin-top: 6px; letter-spacing: 0.5px; text-transform: uppercase;">Practice Count</div>
                    """

                    health_html = _build_health_html(ui_state["component_health"])

                    yield (
                        annotated,
                        feedback_html,
                        history_html,
                        pose if pose else gr.update(),
                        timer_html,
                        fall_html,
                        health_html,
                    )
                else:
                    yield (
                        annotated,
                        gr.update(),
                        gr.update(),
                        gr.update(),
                        gr.update(),
                        gr.update(),
                        gr.update(),
                    )

                time.sleep(0.033)  # ~30fps

        # ── Wire events ──

        start_event = start_btn.click(
            fn=on_start,
            inputs=[study_id_input],
            outputs=[
                qr_output,
                session_code_display,
                connection_status,
                start_btn,
                pause_btn,
                stop_btn,
                status_output,
                export_info,
                feedback_log,
                fall_count_display,
                session_timer_display,
                feedback_banner,
                health_display,
                export_data_btn,
                discard_data_btn,
            ],
        )

        start_event.then(
            fn=update_stream,
            outputs=[
                video_output,
                feedback_banner,
                feedback_log,
                pose_info,
                session_timer_display,
                fall_count_display,
                health_display,
            ],
        )

        pause_btn.click(
            fn=on_pause,
            outputs=[pause_btn],
        )

        stop_btn.click(
            fn=on_stop,
            outputs=[
                video_output,
                feedback_banner,
                connection_status,
                start_btn,
                pause_btn,
                stop_btn,
                status_output,
                export_info,
                health_display,
                export_data_btn,
                discard_data_btn,
            ],
        )

        export_data_btn.click(
            fn=on_export_data,
            outputs=[export_info, export_data_btn, discard_data_btn],
        )

        discard_data_btn.click(
            fn=on_discard_data,
            outputs=[export_info, export_data_btn, discard_data_btn],
        )

        def on_camera_change(selection):
            idx = int(selection.replace("Camera ", ""))
            wizard.set_camera(idx)
            return f"Switched to Camera {idx}"

        camera_dropdown.change(
            fn=on_camera_change,
            inputs=[camera_dropdown],
            outputs=[status_output],
        )

        # Initialize on load — streams health updates progressively as each
        # component finishes, so "Ready" dots appear one at a time.
        demo.load(
            fn=wizard.initialize_streaming,
            outputs=[status_output, health_display],
        )

    return demo


def main():
    """Main entry point."""
    if not HAS_GRADIO:
        print("Please install Gradio: pip install gradio")
        return

    wizard = ActiveLearningWizard()

    try:
        demo = create_gradio_interface(wizard)
        demo.launch(
            server_name="0.0.0.0",
            server_port=7860,
            share=False,
            show_error=True,
        )
    finally:
        wizard.cleanup()


if __name__ == "__main__":
    main()
