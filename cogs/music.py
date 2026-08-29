import logging
import os
from typing import Literal, cast

import discord
import wavelink
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        node = wavelink.Node(
            uri=os.getenv("LAVALINK_URI", "http://127.0.0.1:2333"),
            password=os.getenv("LAVALINK_PASSWORD", "Aru1234"),
        )
        await wavelink.Pool.connect(nodes=[node], client=self.bot)

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload):
        logger.info(f"[Lavalink] Node `{payload.node.identifier}` connected successfully!")

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload):
        # Wavelink AutoPlayMode.partial automatically advances the queue according to player.queue.mode.
        pass

    async def _get_player(self, interaction: discord.Interaction) -> wavelink.Player | None:
        """Helper to get or connect a Wavelink Player."""
        if not interaction.guild:
            return None

        if interaction.guild.voice_client:
            player = cast(wavelink.Player, interaction.guild.voice_client)
            if interaction.user and isinstance(interaction.user, discord.Member) and interaction.user.voice and interaction.user.voice.channel and interaction.user.voice.channel != player.channel:
                await player.move_to(interaction.user.voice.channel)
            return player

        if interaction.user and isinstance(interaction.user, discord.Member) and interaction.user.voice and interaction.user.voice.channel:
            player = cast(wavelink.Player, await interaction.user.voice.channel.connect(cls=wavelink.Player))
            player.autoplay = wavelink.AutoPlayMode.partial
            return player

        return None

    @app_commands.command(name="play", description="เล่นเพลงจากชื่อเพลงหรือลิงก์")
    @app_commands.describe(query="ชื่อเพลง หรือ URL ของเพลง (YouTube/SoundCloud)")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        if not interaction.user or not isinstance(interaction.user, discord.Member) or not interaction.user.voice:
            await interaction.followup.send("คุณต้องเข้าห้องเสียง (Voice Channel) ก่อนนะครับ")
            return

        player = await self._get_player(interaction)
        if player is None:
            await interaction.followup.send("ไม่สามารถเชื่อมต่อห้องเสียงได้")
            return

        try:
            tracks = await wavelink.Playable.search(query)
        except wavelink.WavelinkException as e:
            logger.error(f"Error searching for '{query}': {e}")
            await interaction.followup.send(f"เกิดข้อผิดพลาดขณะค้นหาเพลง: `{e}`")
            return
        except Exception as e:  # noqa: BLE001
            logger.error(f"Unexpected error searching for '{query}': {e}")
            await interaction.followup.send(f"เกิดข้อผิดพลาดขณะค้นหาเพลง: `{e}`")
            return

        if not tracks:
            await interaction.followup.send(f"ไม่พบเพลงที่ค้นหา: `{query}`")
            return

        if isinstance(tracks, wavelink.Playlist):
            added = await player.queue.put_wait(tracks)
            await interaction.followup.send(f"เพิ่มเพลย์ลิสต์ **{tracks.name}** ({added} เพลง) เข้าคิวแล้ว 🎵")
        else:
            track = tracks[0]
            await player.queue.put_wait(track)
            await interaction.followup.send(f"เพิ่มเพลง **{track.title}** เข้าคิวแล้ว 🎵")

        if not player.playing and not player.queue.is_empty:
            next_track = player.queue.get()
            await player.play(next_track)

    @app_commands.command(name="skip", description="ข้ามเพลงปัจจุบัน")
    async def skip(self, interaction: discord.Interaction):
        if not interaction.guild or not interaction.guild.voice_client:
            await interaction.response.send_message("บอทยังไม่ได้อยู่ในห้องเสียง")
            return

        player = cast(wavelink.Player, interaction.guild.voice_client)
        if not player.playing:
            await interaction.response.send_message("ตอนนี้ไม่มีเพลงกำลังเล่นอยู่")
            return

        await player.skip(force=True)
        await interaction.response.send_message("ข้ามเพลงแล้ว ⏭️")

    @app_commands.command(name="stop", description="หยุดเพลงและออกจากห้องเสียง")
    async def stop(self, interaction: discord.Interaction):
        if not interaction.guild or not interaction.guild.voice_client:
            await interaction.response.send_message("บอทยังไม่ได้อยู่ในห้องเสียง")
            return

        player = cast(wavelink.Player, interaction.guild.voice_client)
        player.queue.clear()
        await player.disconnect()
        await interaction.response.send_message("หยุดเพลงและออกจากห้องเสียงแล้ว 👋")

    @app_commands.command(name="pause", description="พักเพลงชั่วคราว")
    async def pause(self, interaction: discord.Interaction):
        if not interaction.guild or not interaction.guild.voice_client:
            await interaction.response.send_message("บอทยังไม่ได้อยู่ในห้องเสียง")
            return

        player = cast(wavelink.Player, interaction.guild.voice_client)
        if not player.playing:
            await interaction.response.send_message("ไม่มีเพลงกำลังเล่นอยู่")
            return

        await player.pause(True)
        await interaction.response.send_message("พักเพลงแล้ว ⏸️")

    @app_commands.command(name="resume", description="เล่นเพลงต่อ")
    async def resume(self, interaction: discord.Interaction):
        if not interaction.guild or not interaction.guild.voice_client:
            await interaction.response.send_message("บอทยังไม่ได้อยู่ในห้องเสียง")
            return

        player = cast(wavelink.Player, interaction.guild.voice_client)
        if not player.paused:
            await interaction.response.send_message("เพลงไม่ได้ถูกพักอยู่")
            return

        await player.pause(False)
        await interaction.response.send_message("เล่นเพลงต่อแล้ว ▶️")

    @app_commands.command(name="loop", description="ตั้งค่าวนซ้ำเพลง (off = ปิด, track = เพลงปัจจุบัน, queue = ทั้งคิว)")
    @app_commands.describe(mode="เลือกโหมดวนซ้ำ: off (ปิด), track (เพลงปัจจุบัน), queue (ทั้งคิว)")
    async def loop(self, interaction: discord.Interaction, mode: Literal["off", "track", "queue"] = "track"):
        if not interaction.guild or not interaction.guild.voice_client:
            await interaction.response.send_message("บอทยังไม่ได้อยู่ในห้องเสียง")
            return

        player = cast(wavelink.Player, interaction.guild.voice_client)

        if mode == "off":
            player.queue.mode = wavelink.QueueMode.normal
            await interaction.response.send_message("ปิดการทำงานวนซ้ำแล้ว ➡️")
        elif mode == "track":
            player.queue.mode = wavelink.QueueMode.loop
            await interaction.response.send_message("เปิดโหมดวนซ้ำ: **เพลงปัจจุบัน** 🔂")
        elif mode == "queue":
            player.queue.mode = wavelink.QueueMode.loop_all
            await interaction.response.send_message("เปิดโหมดวนซ้ำ: **คิวเพลงทั้งหมด** 🔁")

    @app_commands.command(name="queue", description="ดูรายการคิวเพลง")
    async def queue(self, interaction: discord.Interaction):
        if not interaction.guild or not interaction.guild.voice_client:
            await interaction.response.send_message("บอทยังไม่ได้อยู่ในห้องเสียง")
            return

        player = cast(wavelink.Player, interaction.guild.voice_client)
        if not player.current and player.queue.is_empty:
            await interaction.response.send_message("คิวเพลงว่างเปล่า")
            return

        msg_lines = []
        if player.current:
            msg_lines.append(f"🎶 **กำลังเล่น:** {player.current.title}")

        if player.queue.mode == wavelink.QueueMode.loop:
            msg_lines.append("🔂 **โหมดวนซ้ำ:** เพลงปัจจุบัน")
        elif player.queue.mode == wavelink.QueueMode.loop_all:
            msg_lines.append("🔁 **โหมดวนซ้ำ:** ทั้งคิว")

        if not player.queue.is_empty:
            msg_lines.append("\n📜 **คิวเพลงถัดไป:**")
            for i, t in enumerate(list(player.queue)[:10]):
                msg_lines.append(f"{i + 1}. {t.title}")
        else:
            msg_lines.append("\n(ไม่มีเพลงในคิวถัดไป)")

        await interaction.response.send_message("\n".join(msg_lines))

    @app_commands.command(name="nowplaying", description="ดูเพลงที่กำลังเล่นอยู่")
    async def nowplaying(self, interaction: discord.Interaction):
        if not interaction.guild or not interaction.guild.voice_client:
            await interaction.response.send_message("บอทยังไม่ได้อยู่ในห้องเสียง")
            return

        player = cast(wavelink.Player, interaction.guild.voice_client)
        if not player.current:
            await interaction.response.send_message("ไม่มีเพลงกำลังเล่นอยู่ตอนนี้")
            return

        track = player.current
        author = getattr(track, "author", "Unknown Artist")
        await interaction.response.send_message(f"🎶 กำลังเล่น: **{track.title}** โดย *{author}*")

    @app_commands.command(name="volume", description="ปรับระดับเสียง (0-100)")
    @app_commands.describe(level="ระดับเสียงที่ต้องการ (0-100)")
    async def volume(self, interaction: discord.Interaction, level: app_commands.Range[int, 0, 100]):
        if not interaction.guild or not interaction.guild.voice_client:
            await interaction.response.send_message("บอทยังไม่ได้อยู่ในห้องเสียง")
            return

        player = cast(wavelink.Player, interaction.guild.voice_client)
        await player.set_volume(level)
        await interaction.response.send_message(f"ปรับระดับเสียงเป็น {level}% แล้ว 🔊")


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))