import os
import sys
import json
import html
import smtplib
import argparse
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BASE_DIR)
HISTORY_FILE = os.path.join(BASE_DIR, "data", "history.json")
TEMP_DIR = os.path.join(BASE_DIR, "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

sys.path.insert(0, BASE_DIR)
from uploader import get_youtube_access_token
from brain import get_gemini_key

BRT = timezone(timedelta(hours=-3))


def _api_get_json(url, access_token):
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_iso_duration_sec(iso_dur):
    """Converte PT1M12S / PT24S para segundos inteiros."""
    if not iso_dur or not iso_dur.startswith("PT"):
        return 0
    s = iso_dur[2:]
    total = 0
    num = ""
    for ch in s:
        if ch.isdigit():
            num += ch
        else:
            val = int(num or 0)
            num = ""
            if ch == "H":
                total += val * 3600
            elif ch == "M":
                total += val * 60
            elif ch == "S":
                total += val
    return total


def _load_local_history_map():
    if not os.path.exists(HISTORY_FILE):
        return {}
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        by_yt = {}
        for p in data.get("posts", []):
            yt_id = p.get("yt_uploaded_id")
            if yt_id:
                by_yt[yt_id] = p
        return by_yt
    except Exception:
        return {}


def fetch_channel_and_weekly_videos(access_token, days=7):
    """Busca métricas reais do canal + vídeos publicados na janela via YouTube Data API v3."""
    ch_url = "https://www.googleapis.com/youtube/v3/channels?part=snippet,statistics,contentDetails&mine=true"
    ch_data = _api_get_json(ch_url, access_token)
    items = ch_data.get("items") or []
    if not items:
        raise RuntimeError("Nenhum canal encontrado para o token autenticado.")

    ch = items[0]
    channel_info = {
        "id": ch["id"],
        "title": ch["snippet"]["title"],
        "subscribers": int(ch["statistics"].get("subscriberCount", 0)),
        "total_views": int(ch["statistics"].get("viewCount", 0)),
        "total_videos": int(ch["statistics"].get("videoCount", 0)),
    }
    uploads_pl = ch["contentDetails"]["relatedPlaylists"]["uploads"]

    pl_url = (
        "https://www.googleapis.com/youtube/v3/playlistItems"
        f"?part=snippet,contentDetails&playlistId={urllib.parse.quote(uploads_pl)}&maxResults=50"
    )
    pl_data = _api_get_json(pl_url, access_token)

    now_utc = datetime.now(timezone.utc)
    cutoff = now_utc - timedelta(days=days)
    recent_ids = []
    all_ids = []

    for it in pl_data.get("items", []):
        vid = it["contentDetails"]["videoId"]
        pub_str = it["contentDetails"].get("videoPublishedAt") or it["snippet"].get("publishedAt")
        all_ids.append(vid)
        if pub_str:
            pub_dt = datetime.fromisoformat(pub_str.replace("Z", "+00:00"))
            if pub_dt >= cutoff:
                recent_ids.append(vid)

    target_ids = recent_ids if recent_ids else all_ids[:15]
    history_map = _load_local_history_map()
    videos = []

    if target_ids:
        ids_param = ",".join(target_ids[:50])
        v_url = (
            "https://www.googleapis.com/youtube/v3/videos"
            f"?part=snippet,statistics,contentDetails&id={urllib.parse.quote(ids_param)}"
        )
        v_data = _api_get_json(v_url, access_token)
        for v in v_data.get("items", []):
            vid = v["id"]
            stats = v.get("statistics", {})
            pub_dt = datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00")).astimezone(BRT)
            hist_entry = history_map.get(vid, {})
            videos.append({
                "id": vid,
                "url": f"https://youtube.com/shorts/{vid}",
                "title": v["snippet"]["title"],
                "published_brt": pub_dt.strftime("%d/%m %H:%M"),
                "hour_brt": f"{pub_dt.hour:02d}h",
                "duration_sec": _parse_iso_duration_sec(v["contentDetails"].get("duration")),
                "views": int(stats.get("viewCount", 0)),
                "likes": int(stats.get("likeCount", 0)),
                "comments": int(stats.get("commentCount", 0)),
                "source_original_title": hist_entry.get("original_title", ""),
            })

    videos.sort(key=lambda x: x["views"], reverse=True)
    return channel_info, videos, bool(recent_ids)


def fetch_youtube_analytics(access_token, days=7):
    """Busca retenção média, tempo assistido e inscritos ganhos via YouTube Analytics API."""
    end_dt = datetime.now(BRT).date()
    start_dt = end_dt - timedelta(days=days)

    summary_url = (
        "https://youtubeanalytics.googleapis.com/v2/reports"
        f"?ids=channel==MINE&startDate={start_dt}&endDate={end_dt}"
        "&metrics=views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained"
    )
    by_video_url = (
        "https://youtubeanalytics.googleapis.com/v2/reports"
        f"?ids=channel==MINE&startDate={start_dt}&endDate={end_dt}"
        "&metrics=views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained"
        "&dimensions=video&sort=-views&maxResults=40"
    )

    try:
        sum_data = _api_get_json(summary_url, access_token)
        vid_data = _api_get_json(by_video_url, access_token)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")[:300]
        return {"enabled": False, "error": f"HTTP {e.code}: {body}", "by_video": {}}
    except Exception as e:
        return {"enabled": False, "error": str(e), "by_video": {}}

    sum_rows = sum_data.get("rows") or []
    totals = {
        "views": int(sum_rows[0][0]) if sum_rows else 0,
        "watch_minutes": round(float(sum_rows[0][1]), 1) if sum_rows else 0.0,
        "avg_view_sec": round(float(sum_rows[0][2]), 1) if sum_rows else 0.0,
        "avg_retention_pct": round(float(sum_rows[0][3]), 1) if sum_rows else 0.0,
        "subs_gained": int(sum_rows[0][4]) if sum_rows else 0,
    }

    by_video = {}
    for row in vid_data.get("rows") or []:
        by_video[row[0]] = {
            "analytics_views": int(row[1]),
            "watch_minutes": round(float(row[2]), 1),
            "avg_view_sec": round(float(row[3]), 1),
            "retention_pct": round(float(row[4]), 1),
            "subs_gained": int(row[5]),
        }

    return {"enabled": True, "totals": totals, "by_video": by_video}


def fetch_sample_comments(access_token, video_ids, limit_videos=3):
    comments = []
    for vid in video_ids[:limit_videos]:
        try:
            url = (
                "https://www.googleapis.com/youtube/v3/commentThreads"
                f"?part=snippet&videoId={vid}&maxResults=3&order=relevance"
            )
            data = _api_get_json(url, access_token)
            for it in data.get("items", []):
                sn = it["snippet"]["topLevelComment"]["snippet"]
                comments.append({
                    "video_id": vid,
                    "author": sn.get("authorDisplayName", "Inscrito"),
                    "text": (sn.get("textDisplay") or "").replace("<br>", " ")[:180],
                    "likes": int(sn.get("likeCount", 0)),
                })
        except Exception:
            pass
    return comments


def build_weekly_metrics(days=7):
    token = get_youtube_access_token(1)
    channel, videos, has_recent = fetch_channel_and_weekly_videos(token, days=days)
    analytics = fetch_youtube_analytics(token, days=days)

    an_map = analytics.get("by_video", {})
    for v in videos:
        a = an_map.get(v["id"], {})
        v["retention_pct"] = a.get("retention_pct")
        v["avg_view_sec"] = a.get("avg_view_sec")
        v["subs_gained"] = a.get("subs_gained", 0)

    total_week_views = sum(v["views"] for v in videos)
    total_week_likes = sum(v["likes"] for v in videos)
    total_week_comments = sum(v["comments"] for v in videos)

    hour_buckets = {}
    for v in videos:
        hb = hour_buckets.setdefault(v["hour_brt"], {"count": 0, "views": 0})
        hb["count"] += 1
        hb["views"] += v["views"]
    hour_summary = [
        {"hour": h, "videos": d["count"], "avg_views": round(d["views"] / max(1, d["count"]))}
        for h, d in sorted(hour_buckets.items())
    ]

    top_ids = [v["id"] for v in videos[:3] if v["comments"] > 0]
    comments = fetch_sample_comments(token, top_ids)

    now_brt = datetime.now(BRT)
    start_brt = now_brt - timedelta(days=days)

    return {
        "period_label": f"{start_brt.strftime('%d/%m')} a {now_brt.strftime('%d/%m/%Y')}",
        "has_recent_7d": has_recent,
        "channel": channel,
        "analytics": analytics,
        "summary": {
            "videos_count": len(videos),
            "views": total_week_views,
            "likes": total_week_likes,
            "comments": total_week_comments,
            "avg_views_per_video": round(total_week_views / max(1, len(videos))),
        },
        "top_videos": videos[:3],
        "bottom_videos": list(reversed(videos[-3:])) if len(videos) > 3 else [],
        "all_videos": videos,
        "hour_summary": hour_summary,
        "sample_comments": comments,
    }


def generate_ai_recommendations(metrics):
    """Pede ao Gemini análise objetiva 100% ancorada nos números reais coletados."""
    api_key = get_gemini_key()
    compact_payload = {
        "period": metrics["period_label"],
        "channel": metrics["channel"],
        "analytics_enabled": metrics["analytics"]["enabled"],
        "analytics_totals": metrics["analytics"].get("totals"),
        "summary": metrics["summary"],
        "top_videos": metrics["top_videos"],
        "bottom_videos": metrics["bottom_videos"],
        "hour_summary": metrics["hour_summary"],
        "sample_comments": metrics["sample_comments"],
    }

    prompt = f"""Você é o Diretor de Crescimento e Monetização (YouTube Shorts BR) do canal "{metrics['channel']['title']}".
Analise EXATAMENTE os dados reais abaixo da semana (PROIBIDO inventar métricas ou números que não estão no JSON).
NUNCA mencione nomes internos de campos/variáveis do JSON (como "source_original_title", "avg_view_sec" ou nomes de arquivos) — fale sempre em linguagem humana e estratégica para o dono do canal.

DADOS REAIS:
{json.dumps(compact_payload, ensure_ascii=False, indent=2)}

Retorne APENAS um JSON válido em português com estas chaves:
{{
  "resumo_executivo": "2 a 3 frases objetivas sobre o momento do canal citando números reais.",
  "porque_campeao_funcionou": "Explicação direta do que fez o vídeo #1 ir melhor (título, gancho, tema ou horário).",
  "diagnostico_retencao": "Leitura sincera dos vídeos fracos ou da retenção média (ou aviso se ainda há poucos vídeos).",
  "sugestoes_conteudo": [
    "Sugestão prática 1 de tema/estilo para priorizar nos próximos dias",
    "Sugestão prática 2 de gancho/título baseada no que teve mais engajamento",
    "Sugestão prática 3 de ajuste técnico ou de garimpo no ReactFactory"
  ],
  "melhor_horario": "Qual horário entre 09h e 19h performou melhor (ou orientação inicial se empate)."
}}"""

    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "responseMimeType": "application/json"},
    }

    for model_name in ["gemini-2.5-flash", "gemini-3.5-flash"]:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
            req = urllib.request.Request(
                url,
                data=json.dumps(body).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
                txt = raw["candidates"][0]["content"]["parts"][0]["text"].strip()
                if txt.startswith("```"):
                    txt = txt.strip("`").lstrip("json").strip()
                return json.loads(txt)
        except Exception as e:
            print(f"[ANALYST] Fallback Gemini ({model_name}: {e})")

    return {
        "resumo_executivo": f"Foram analisados {metrics['summary']['videos_count']} vídeos com {metrics['summary']['views']:,} views acumuladas.",
        "porque_campeao_funcionou": "Título direto de curiosidade e melhor resposta inicial do algoritmo.",
        "diagnostico_retencao": "Continue monitorando a relação views x retenção nas primeiras 48h após cada upload.",
        "sugestoes_conteudo": [
            "Dobrar a aposta nos formatos semelhantes ao Top 1 da semana.",
            "Manter hooks curtos abaixo de 8 palavras e perguntas no final para comentários.",
            "Acompanhar por 7 dias completos para consolidar horários campeões.",
        ],
        "melhor_horario": "Ainda em fase de coleta inicial.",
    }


def _fmt_int(n):
    return f"{int(n):,}".replace(",", ".")


def render_html_report(metrics, ai_notes, is_preview=False):
    ch = metrics["channel"]
    sm = metrics["summary"]
    an = metrics["analytics"]
    totals = an.get("totals", {}) if an.get("enabled") else {}

    ret_display = f"{totals['avg_retention_pct']:.1f}%" if an.get("enabled") else "Pendente OAuth"
    watch_display = f"{totals['avg_view_sec']:.1f}s" if an.get("enabled") else "Pendente OAuth"
    subs_delta = f"+{totals.get('subs_gained', 0)} na semana" if an.get("enabled") else f"{_fmt_int(ch['total_videos'])} vídeos no canal"

    def video_row_html(v, badge_color="#2563EB", rank=None):
        if v.get("retention_pct") is not None:
            ret_cell = f"{v['retention_pct']:.1f}%<br><span style='font-size:11px;color:#64748B;'>{v['avg_view_sec']:.1f}s</span>"
        else:
            ret_cell = "<span style='color:#94A3B8;font-size:12px;'>~48h</span>"
        rank_badge = f"<span style='display:inline-block;background:{badge_color};color:#fff;font-weight:700;font-size:11px;padding:2px 8px;border-radius:999px;margin-right:8px;'>#{rank}</span>" if rank else ""
        return f"""
        <tr>
          <td style="padding:14px 12px;border-bottom:1px solid #E2E8F0;vertical-align:top;">
            <div style="margin-bottom:4px;">{rank_badge}<a href="{html.escape(v['url'])}" style="color:#0F172A;font-weight:700;font-size:14px;text-decoration:none;">{html.escape(v['title'])}</a></div>
            <div style="font-size:12px;color:#64748B;">Publicado: {html.escape(v['published_brt'])} BRT &bull; Duração: {v['duration_sec']}s</div>
          </td>
          <td style="padding:14px 10px;border-bottom:1px solid #E2E8F0;text-align:right;font-weight:700;color:#0F172A;font-size:14px;white-space:nowrap;">{_fmt_int(v['views'])}</td>
          <td style="padding:14px 10px;border-bottom:1px solid #E2E8F0;text-align:right;color:#0F172A;font-size:13px;white-space:nowrap;">{ret_cell}</td>
          <td style="padding:14px 10px;border-bottom:1px solid #E2E8F0;text-align:right;color:#334155;font-size:13px;white-space:nowrap;">👍 {_fmt_int(v['likes'])}<br>💬 {_fmt_int(v['comments'])}</td>
        </tr>"""

    top_rows = "".join(video_row_html(v, "#16A34A", idx + 1) for idx, v in enumerate(metrics["top_videos"]))
    bot_rows = "".join(video_row_html(v, "#DC2626", "↓") for v in metrics["bottom_videos"])

    hours_html = "".join(
        f"<span style='display:inline-block;background:#F1F5F9;border:1px solid #CBD5E1;border-radius:8px;padding:6px 10px;margin:0 6px 6px 0;font-size:12px;color:#0F172A;'><strong>{html.escape(h['hour'])}</strong>: {_fmt_int(h['avg_views'])} views/vídeo ({h['videos']}x)</span>"
        for h in metrics["hour_summary"]
    ) or "<span style='font-size:13px;color:#64748B;'>Sem variação de horários ainda.</span>"

    comments_html = "".join(
        f"<div style='background:#F8FAFC;border-left:3px solid #F59E0B;padding:10px 12px;margin-bottom:8px;border-radius:0 8px 8px 0;font-size:13px;color:#1E293B;'><strong>{html.escape(c['author'])}:</strong> “{html.escape(c['text'])}”</div>"
        for c in metrics["sample_comments"]
    ) or "<div style='font-size:13px;color:#64748B;'>Nenhum comentário relevante registrado nesta amostra ainda.</div>"

    suggestions_html = "".join(
        f"<li style='margin-bottom:10px;line-height:1.5;color:#1E293B;'>{html.escape(s)}</li>"
        for s in ai_notes.get("sugestoes_conteudo", [])
    )

    preview_banner = (
        "<div style='background:#FEF3C7;color:#92400E;padding:10px 16px;font-size:12px;font-weight:700;text-align:center;border-bottom:1px solid #FDE68A;'>MODO PRÉ-VISUALIZAÇÃO — Dados reais atuais do canal antes do primeiro ciclo semanal completo</div>"
        if is_preview
        else ""
    )

    analytics_notice = (
        ""
        if an.get("enabled")
        else "<div style='background:#EFF6FF;border:1px solid #BFDBFE;color:#1E40AF;padding:10px 14px;border-radius:8px;font-size:12px;margin-top:12px;'>ℹ️ Retenção % e Tempo Médio Assistido aparecerão aqui automaticamente assim que concluirmos a reautorização OAuth com o escopo Analytics.</div>"
    )

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Relatório Semanal — {html.escape(ch['title'])}</title>
</head>
<body style="margin:0;padding:0;background-color:#F1F5F9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#F1F5F9;padding:24px 12px;">
    <tr>
      <td align="center">
        <table role="presentation" width="660" cellspacing="0" cellpadding="0" style="max-width:660px;width:100%;background:#FFFFFF;border-radius:16px;overflow:hidden;box-shadow:0 8px 30px rgba(15,23,42,0.08);">
          {preview_banner}
          <!-- HEADER -->
          <tr>
            <td style="background:linear-gradient(135deg,#0F172A 0%,#1E293B 100%);padding:28px 30px;color:#FFFFFF;">
              <div style="font-size:11px;letter-spacing:1.8px;text-transform:uppercase;color:#FACC15;font-weight:700;margin-bottom:6px;">VELLI ANALYTICS // RELATÓRIO DOMINICAL DE PERFORMANCE</div>
              <h1 style="margin:0;font-size:24px;line-height:1.25;font-weight:800;color:#FFFFFF;">Canal {html.escape(ch['title'])}</h1>
              <div style="margin-top:8px;font-size:13px;color:#CBD5E1;">Período analisado: <strong style="color:#FFFFFF;">{html.escape(metrics['period_label'])}</strong> &bull; {sm['videos_count']} vídeos avaliados</div>
            </td>
          </tr>

          <!-- KPI GRID -->
          <tr>
            <td style="padding:24px 26px 8px 26px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0">
                <tr>
                  <td width="25%" style="padding:4px;">
                    <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:12px;padding:14px 10px;text-align:center;">
                      <div style="font-size:11px;color:#64748B;text-transform:uppercase;font-weight:700;">Views Semana</div>
                      <div style="font-size:22px;font-weight:800;color:#0F172A;margin-top:4px;">{_fmt_int(sm['views'])}</div>
                      <div style="font-size:11px;color:#16A34A;margin-top:2px;">~{_fmt_int(sm['avg_views_per_video'])}/vídeo</div>
                    </div>
                  </td>
                  <td width="25%" style="padding:4px;">
                    <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:12px;padding:14px 10px;text-align:center;">
                      <div style="font-size:11px;color:#64748B;text-transform:uppercase;font-weight:700;">Inscritos</div>
                      <div style="font-size:22px;font-weight:800;color:#0F172A;margin-top:4px;">{_fmt_int(ch['subscribers'])}</div>
                      <div style="font-size:11px;color:#475569;margin-top:2px;">{html.escape(subs_delta)}</div>
                    </div>
                  </td>
                  <td width="25%" style="padding:4px;">
                    <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:12px;padding:14px 10px;text-align:center;">
                      <div style="font-size:11px;color:#64748B;text-transform:uppercase;font-weight:700;">Retenção Média</div>
                      <div style="font-size:20px;font-weight:800;color:#DC2626;margin-top:4px;">{html.escape(ret_display)}</div>
                      <div style="font-size:11px;color:#64748B;margin-top:2px;">Meta: &gt;95%</div>
                    </div>
                  </td>
                  <td width="25%" style="padding:4px;">
                    <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:12px;padding:14px 10px;text-align:center;">
                      <div style="font-size:11px;color:#64748B;text-transform:uppercase;font-weight:700;">Tempo Médio</div>
                      <div style="font-size:20px;font-weight:800;color:#0F172A;margin-top:4px;">{html.escape(watch_display)}</div>
                      <div style="font-size:11px;color:#64748B;margin-top:2px;">👍 {_fmt_int(sm['likes'])} &bull; 💬 {_fmt_int(sm['comments'])}</div>
                    </div>
                  </td>
                </tr>
              </table>
              {analytics_notice}
            </td>
          </tr>

          <!-- RESUMO IA -->
          <tr>
            <td style="padding:18px 30px;">
              <div style="background:#FFFBEB;border-left:4px solid #F59E0B;border-radius:0 12px 12px 0;padding:16px 18px;">
                <div style="font-size:12px;font-weight:800;text-transform:uppercase;color:#B45309;margin-bottom:6px;">Resumo Executivo da Semana</div>
                <p style="margin:0;font-size:14px;line-height:1.6;color:#1E293B;">{html.escape(ai_notes.get('resumo_executivo', ''))}</p>
              </div>
            </td>
          </tr>

          <!-- TOP 3 CAMPEÕES -->
          <tr>
            <td style="padding:8px 30px 18px 30px;">
              <h2 style="margin:0 0 10px 0;font-size:16px;color:#0F172A;">🏆 Top Vídeos que Mais Performaram</h2>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border:1px solid #E2E8F0;border-radius:10px;overflow:hidden;">
                <thead>
                  <tr style="background:#F8FAFC;font-size:11px;text-transform:uppercase;color:#64748B;">
                    <th align="left" style="padding:10px 12px;">Vídeo</th>
                    <th align="right" style="padding:10px;">Views</th>
                    <th align="right" style="padding:10px;">Retenção</th>
                    <th align="right" style="padding:10px;">Engaj.</th>
                  </tr>
                </thead>
                <tbody>{top_rows}</tbody>
              </table>
              <p style="margin:10px 0 0 0;font-size:13px;line-height:1.5;color:#334155;"><strong>Por que o #1 venceu:</strong> {html.escape(ai_notes.get('porque_campeao_funcionou', ''))}</p>
            </td>
          </tr>

          <!-- MENOR DESEMPENHO (SE HOUVER >3 VÍDEOS) -->
          {"" if not bot_rows else f'''
          <tr>
            <td style="padding:4px 30px 18px 30px;">
              <h2 style="margin:0 0 10px 0;font-size:16px;color:#0F172A;">📉 Menor Alcance na Semana (O que Ajustar)</h2>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="border:1px solid #E2E8F0;border-radius:10px;overflow:hidden;">
                <tbody>{bot_rows}</tbody>
              </table>
              <p style="margin:10px 0 0 0;font-size:13px;line-height:1.5;color:#334155;"><strong>Diagnóstico:</strong> {html.escape(ai_notes.get('diagnostico_retencao', ''))}</p>
            </td>
          </tr>'''}

          <!-- HORÁRIOS + COMENTÁRIOS -->
          <tr>
            <td style="padding:4px 30px 18px 30px;">
              <h2 style="margin:0 0 8px 0;font-size:15px;color:#0F172A;">⏰ Desempenho por Horário</h2>
              <div style="margin-bottom:8px;">{hours_html}</div>
              <div style="font-size:13px;color:#475569;margin-bottom:16px;">{html.escape(ai_notes.get('melhor_horario', ''))}</div>

              <h2 style="margin:0 0 8px 0;font-size:15px;color:#0F172A;">💬 O que o Público Comentou</h2>
              {comments_html}
            </td>
          </tr>

          <!-- PLANO PRÓXIMA SEMANA -->
          <tr>
            <td style="padding:8px 30px 28px 30px;">
              <div style="background:#0F172A;color:#FFFFFF;border-radius:12px;padding:20px 22px;">
                <div style="font-size:12px;font-weight:800;text-transform:uppercase;color:#38BDF8;letter-spacing:1px;margin-bottom:10px;">🚀 Sugestões de Conteúdo para Soltar na Próxima Semana</div>
                <ol style="margin:0;padding-left:18px;font-size:14px;color:#E2E8F0;">
                  {suggestions_html.replace('color:#1E293B;', 'color:#F8FAFC;')}
                </ol>
              </div>
            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td style="background:#F8FAFC;padding:16px 30px;text-align:center;border-top:1px solid #E2E8F0;font-size:11px;color:#64748B;">
              Relatório automático dominical gerado pelo <strong>Velli Analytics</strong> &bull; Dados oficiais via YouTube Data &amp; Analytics API
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _load_email_config():
    sender = os.environ.get("EMAIL_SENDER")
    password = os.environ.get("EMAIL_PASSWORD")
    dest_raw = os.environ.get("DESTINATION_EMAILS")

    env_file = os.path.join(ROOT_DIR, "VelliIntelligence", ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    if k.strip() == "EMAIL_REMETENTE" and not sender:
                        sender = v.strip()
                    elif k.strip() == "EMAIL_SENHA_APP" and not password:
                        password = v.strip()

    if not dest_raw:
        raise RuntimeError("DESTINATION_EMAILS não configurado (defina nos GitHub Secrets ou env).")
    destinations = [d.strip() for d in dest_raw.split(",") if d.strip()]
    return sender, password, destinations


def send_weekly_email(html_content, subject):
    sender, password, destinations = _load_email_config()
    if not sender or not password or not destinations:
        raise RuntimeError("EMAIL_SENDER, EMAIL_PASSWORD ou DESTINATION_EMAILS não configurados.")

    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(sender, password)
    for dest in destinations:
        msg = MIMEMultipart("alternative")
        msg["From"] = f"Velli Analytics <{sender}>"
        msg["To"] = dest
        msg["Subject"] = subject
        msg.attach(MIMEText(html_content, "html", "utf-8"))
        server.sendmail(sender, dest, msg.as_string())
        print(f"[ANALYST] E-mail semanal enviado para: {dest}")
    server.quit()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true", help="Envia o relatório semanal por e-mail.")
    parser.add_argument("--preview", action="store_true", help="Salva HTML de prévia sem enviar e-mail.")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    print("[ANALYST] Coletando métricas reais do canal no YouTube...")
    metrics = build_weekly_metrics(days=args.days)
    print(f"[ANALYST] Canal: {metrics['channel']['title']} | Vídeos={metrics['summary']['videos_count']} | Views={metrics['summary']['views']} | Analytics ativo={metrics['analytics']['enabled']}")

    ai_notes = generate_ai_recommendations(metrics)
    html_out = render_html_report(metrics, ai_notes, is_preview=args.preview)

    preview_path = os.path.join(TEMP_DIR, "weekly_report_preview.html")
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(html_out)
    print(f"[ANALYST] HTML salvo em: {preview_path}")

    if args.send:
        subject = f"📊 Velli Analytics: Cortes Todo Dia ({metrics['period_label']}) — {_fmt_int(metrics['summary']['views'])} views"
        send_weekly_email(html_out, subject)


if __name__ == "__main__":
    main()
