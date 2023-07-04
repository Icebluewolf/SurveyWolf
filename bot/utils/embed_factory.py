import discord
from discord.ext.pages import Paginator


async def _paginate(em: discord.Embed, value: str | list[tuple]) -> list[str]:
    async def get_chunks(text: str) -> list[str]:
        # Total Characters In An Embed Can Be Maximum Of 6000
        # I Am limiting Chunks To 4096 Even If There Is Extra Space So I Can Use Description
        max_chunk_size = min(4096, 6000 - total_chars)
        chunks = []
        while len(text) > max_chunk_size:
            delimiter_index = max(
                text.rfind("\n", 0, max_chunk_size), text.rfind(".", 0, max_chunk_size)
            )
            if delimiter_index == -1:
                delimiter_index = text.rfind(" ", 0, max_chunk_size)
                if delimiter_index == -1:
                    delimiter_index = max_chunk_size
            chunks.append(text[:delimiter_index])
            text = text[delimiter_index:]
        chunks.append(text)
        return chunks

    total_chars = len(em.title) + len(em.footer.text) + len(em.author.name)

    if type(value) == str:
        chunks = await get_chunks(value)
        for chunk in chunks:
            new_em = em.copy()
            new_em.description = chunk
            chunk = new_em

    elif type(value) == list[tuple]:
        for i in value:
            if len(i[0]) + len(i[1]) > 6000 - total_chars:
                # use string chunk function
                pass


async def error(traceback: str, **kwargs) -> discord.Embed:
    e = discord.Embed(color=0xFF0000, title="Error")
    e.set_footer(text="Report This In The Support Server")
    e.add_field(inline=False, name="Error:", value=traceback)
    return e


async def fail(message: str, **kwargs) -> discord.Embed:
    return discord.Embed(
        color=0xD33033, title="You Can Not Do That", description=message
    )


async def success(message: str = None, **kwargs) -> discord.Embed:
    return discord.Embed(color=0x00FF00, title="Success!", description=message)


async def general(title: str, message: str, **kwargs) -> discord.Embed:
    return discord.Embed(color=0x30D3D0, title=title, description=message)
