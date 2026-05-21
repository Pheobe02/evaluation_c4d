"""
YouTube Newsletter Generator - Main Script
Ties together all the pieces: fetch videos → get transcripts → write articles → send email
Tracks processed videos to avoid sending duplicates.
"""

import argparse
from urllib.parse import urlparse, parse_qs

from get_videos import main as fetch_videos, fetch_video_by_id
from get_transcripts import get_transcripts_for_videos
from write_articles import write_articles_for_videos
from send_email import send_newsletter, create_epub, create_newsletter_html, save_newsletter_archive
from video_tracker import filter_new_videos, mark_videos_processed, get_processed_count


def extract_video_id(video_input):
    """
    Extract a YouTube video ID from a URL or return the input if it's already an ID.
    """
    if not video_input:
        return None

    # Likely already an ID
    if "://" not in video_input and "/" not in video_input:
        return video_input

    try:
        parsed = urlparse(video_input)
        host = parsed.netloc.lower()
        path = parsed.path.strip("/")

        # youtu.be/<id>
        if "youtu.be" in host and path:
            return path.split("/")[0]

        # youtube.com/watch?v=<id>
        if "youtube.com" in host:
            if path == "watch":
                qs = parse_qs(parsed.query)
                return (qs.get("v") or [None])[0]
            # youtube.com/shorts/<id> or /embed/<id>
            if path.startswith("shorts/") or path.startswith("embed/"):
                return path.split("/")[1]
    except Exception:
        return None

    return None


def run():
    """
    Run the full newsletter pipeline.
    """
    parser = argparse.ArgumentParser(description="YouTube to Ebook")
    parser.add_argument("--video-url", "--video", dest="video_url", help="Process a single YouTube video URL")
    parser.add_argument("--video-id", dest="video_id", help="Process a single YouTube video ID")
    parser.add_argument("--epub-only", action="store_true", help="Generate an EPUB locally without sending email")
    parser.add_argument("--recipient", dest="recipient_email", help="Send the newsletter to a specific email")
    args = parser.parse_args()

    print("=" * 60)
    print("  YOUTUBE NEWSLETTER GENERATOR")
    print("=" * 60)
    print(f"  Previously processed: {get_processed_count()} videos")

    single_video = False

    # Step 1: Fetch videos
    print("\n📺 STEP 1: Fetching videos...\n")
    if args.video_url or args.video_id:
        single_video = True
        video_id = args.video_id or extract_video_id(args.video_url)
        if not video_id:
            print("Invalid YouTube URL or video ID.")
            return

        video = fetch_video_by_id(video_id)
        if not video:
            print("Video not found. Check the video ID or URL.")
            return
        videos = [video]
        print(f"  ✓ Found: {video['title']}")
        print(f"    URL: {video['url']}\n")
    else:
        videos = fetch_videos()

    if not videos:
        print("No videos found. Check your channel list.")
        return

    # Step 1b: Filter out already-processed videos (skip for explicit single video)
    if single_video:
        new_videos = videos
    else:
        print("\n🔍 Checking for new videos...\n")
        new_videos = filter_new_videos(videos)

        if not new_videos:
            print("No new videos to process. All videos have been sent before.")
            print("=" * 60)
            return

        print(f"\n  → {len(new_videos)} new video(s) to process\n")

    # Step 2: Get transcripts for those videos
    print("\n📝 STEP 2: Extracting transcripts...\n")
    videos_with_transcripts = get_transcripts_for_videos(new_videos)

    if not videos_with_transcripts:
        print("No transcripts available for any videos.")
        return

    # Step 3: Generate articles using Claude AI
    print("\n✍️ STEP 3: Writing articles with Claude AI...\n")
    articles = write_articles_for_videos(videos_with_transcripts)

    if not articles:
        print("No articles generated.")
        return

    # Step 4: Send email or generate local EPUB
    if args.epub_only:
        print("\n📚 STEP 4: Creating EPUB (no email)...\n")
        epub_path = create_epub(articles)
        html_content = create_newsletter_html(articles)
        save_newsletter_archive(html_content, epub_path, articles)
        print(f"\n  ✓ EPUB saved at: {epub_path}")
        success = True
    else:
        print("\n📧 STEP 4: Sending newsletter...\n")
        success = send_newsletter(articles, recipient_email=args.recipient_email)

    # Step 5: Mark videos as processed (only if email sent successfully)
    if success:
        mark_videos_processed(videos_with_transcripts)
        print(f"\n  ✓ Marked {len(videos_with_transcripts)} video(s) as processed")

    print("\n" + "=" * 60)
    print("  DONE!")
    print("=" * 60)

    return articles


if __name__ == "__main__":
    run()
