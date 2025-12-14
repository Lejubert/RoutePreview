#!/usr/bin/env python3
"""
Regenerate video from existing images folder without re-downloading
Useful for: adding music, changing FPS, or fixing corrupted videos
"""

import sys
import json
import argparse
from pathlib import Path
import subprocess

def create_video_from_images(image_dir: Path, output_path: Path, fps: int = 10, 
                            audio_path: Path = None) -> bool:
    """Create video from images using FFmpeg."""
    images = sorted(image_dir.glob("*.jpg"))
    
    if not images:
        print(f"❌ No images found in {image_dir}")
        return False
    
    print(f"✅ Found {len(images)} images")
    
    # Create file list for FFmpeg
    list_file = image_dir / "images.txt"
    with open(list_file, "w") as f:
        for img in images:
            f.write(f"file '{img.absolute()}'\n")
            f.write(f"duration {1/fps}\n")
    
    # Base FFmpeg command
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(list_file),
        "-vf", "scale=640:640:force_original_aspect_ratio=decrease,pad=640:640:(ow-iw)/2:(oh-ih)/2",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-r", str(fps),
    ]
    
    # Add audio if provided
    if audio_path and audio_path.exists():
        print(f"🎵 Adding audio: {audio_path}")
        cmd.extend(["-i", str(audio_path), "-c:a", "aac", "-shortest"])
    
    cmd.append(str(output_path))
    
    print(f"🎥 Creating video: {output_path}")
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✅ Video created successfully!")
            print(f"   Size: {output_path.stat().st_size / (1024*1024):.2f} MB")
            return True
        else:
            print(f"❌ FFmpeg error:")
            print(result.stderr)
            return False
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


def list_projects():
    """List all available projects."""
    projects_dir = Path("projects")
    
    if not projects_dir.exists():
        print("❌ No projects directory found")
        return []
    
    projects = []
    for project_dir in sorted(projects_dir.iterdir()):
        if project_dir.is_dir():
            metadata_path = project_dir / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path) as f:
                    metadata = json.load(f)
                projects.append({
                    "id": project_dir.name,
                    "path": project_dir,
                    "metadata": metadata
                })
    
    return projects


def main():
    parser = argparse.ArgumentParser(
        description="Regenerate video from existing images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # List all projects
  python regenerate_video.py --list
  
  # Regenerate latest project with different FPS
  python regenerate_video.py --project santamonicapier_venicebeachboardwalk_20251214_074335 --fps 20
  
  # Add music to existing project
  python regenerate_video.py --project <project_id> --audio audio_samples/upbeat.mp3
  
  # Change both FPS and add music
  python regenerate_video.py --project <project_id> --fps 15 --audio my_music.mp3
        """
    )
    
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all available projects"
    )
    
    parser.add_argument(
        "--project", "-p",
        type=str,
        help="Project ID to regenerate (from projects/ folder)"
    )
    
    parser.add_argument(
        "--fps",
        type=int,
        default=None,
        help="Frames per second (default: use original setting)"
    )
    
    parser.add_argument(
        "--audio", "-a",
        type=str,
        help="Path to audio file (MP3)"
    )
    
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output video filename (default: video_regenerated.mp4)"
    )
    
    args = parser.parse_args()
    
    # List projects
    if args.list:
        projects = list_projects()
        
        if not projects:
            print("No projects found!")
            return
        
        print(f"\n{'='*70}")
        print(f"Found {len(projects)} project(s):")
        print(f"{'='*70}\n")
        
        for i, project in enumerate(projects, 1):
            meta = project["metadata"]
            print(f"{i}. {project['id']}")
            print(f"   Route: {meta['route']['start']} → {meta['route']['end']}")
            print(f"   Distance: {meta['route']['distance']}")
            print(f"   Images: {meta['images']['successful']}")
            print(f"   FPS: {meta['settings']['fps']}")
            print(f"   Cost: ${meta['costs']['total']}")
            print()
        
        print("To regenerate, use: python regenerate_video.py --project <project_id>\n")
        return
    
    # Regenerate project
    if not args.project:
        print("❌ Please specify --project <project_id> or use --list to see available projects")
        parser.print_help()
        return
    
    project_dir = Path("projects") / args.project
    
    if not project_dir.exists():
        print(f"❌ Project not found: {args.project}")
        print("   Use --list to see available projects")
        return
    
    # Load metadata
    metadata_path = project_dir / "metadata.json"
    if metadata_path.exists():
        with open(metadata_path) as f:
            metadata = json.load(f)
        print(f"\n📁 Project: {args.project}")
        print(f"   Route: {metadata['route']['start']} → {metadata['route']['end']}")
        print(f"   Distance: {metadata['route']['distance']}\n")
    else:
        metadata = None
    
    # Get settings
    images_dir = project_dir / "images"
    
    if not images_dir.exists():
        print(f"❌ Images directory not found: {images_dir}")
        return
    
    # FPS
    if args.fps:
        fps = args.fps
    elif metadata and "settings" in metadata:
        fps = metadata["settings"]["fps"]
    else:
        fps = 10
    
    print(f"⚙️  Settings: FPS = {fps}")
    
    # Audio
    audio_path = None
    if args.audio:
        audio_path = Path(args.audio)
        if not audio_path.exists():
            print(f"⚠️  Audio file not found: {audio_path}")
            print("   Continuing without audio...")
            audio_path = None
    
    # Output
    if args.output:
        output_filename = args.output
    else:
        output_filename = "video_regenerated.mp4"
    
    output_path = project_dir / output_filename
    
    # Create video
    print()
    success = create_video_from_images(images_dir, output_path, fps, audio_path)
    
    if success:
        print(f"\n✅ Video saved to: {output_path}")
        print(f"\nYou can now:")
        print(f"  - View it: open {output_path}")
        print(f"  - Or regenerate with different settings")
    else:
        print("\n❌ Failed to create video")
        print("   Make sure FFmpeg is installed: brew install ffmpeg")


if __name__ == "__main__":
    main()

