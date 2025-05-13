import discord


async def _paginate(em: discord.Embed, value: str | list[tuple]) -> list[str]:
    async def get_chunks(text: str) -> list[str]:
        # Total Characters In An Embed Can Be Maximum Of 6000
        # I Am limiting Chunks To 4096 Even If There Is Extra Space So I Can Use Description
        max_chunk_size = min(4096, 6000 - total_chars)
        chunks = []
        while len(text) > max_chunk_size:
            delimiter_index = max(text.rfind("\n", 0, max_chunk_size), text.rfind(".", 0, max_chunk_size))
            if delimiter_index == -1:
                delimiter_index = text.rfind(" ", 0, max_chunk_size)
                if delimiter_index == -1:
                    delimiter_index = max_chunk_size
            chunks.append(text[:delimiter_index])
            text = text[delimiter_index:]
        chunks.append(text)
        return chunks

    total_chars = len(em.title) + len(em.footer.text) + len(em.author.name)

    if type(value) is str:
        chunks = await get_chunks(value)
        for chunk in chunks:
            new_em = em.copy()
            new_em.description = chunk
            chunk = new_em

    elif type(value) is list[tuple]:
        for i in value:
            if len(i[0]) + len(i[1]) > 6000 - total_chars:
                # use string chunk function
                pass


async def error(traceback: str) -> discord.ui.Container:
    c = discord.ui.Container(color=0xFF0000)
    c.add_text("## Error\n-# Please Report This In The Support Server")
    c.add_separator()
    c.add_text(f"```\n{traceback}\n```")
    return c


async def input_error(message: str, errors: list[str]) -> discord.ui.Container:
    c = discord.ui.Container(color=0xD33033)
    c.add_text(f"## {message}")
    c.add_separator(divider=False)
    c.add_text("- " + "\n- ".join(errors))
    return c


async def fail(message: str, **kwargs) -> discord.ui.Container:
    c = discord.ui.Container(color=0xD33033)
    c.add_text("## You Can Not Do That")
    c.add_separator(divider=False)
    c.add_text(message)
    return c


async def success(message: str = None, **kwargs) -> discord.ui.Container:
    c = discord.ui.Container(color=0x00FF00)
    c.add_text("## Success!")
    c.add_separator(divider=False)
    if message:
        c.add_text(message)
    return c


async def general(title: str, message: str = None, **kwargs) -> discord.ui.Container:
    c = discord.ui.Container(color=0x30D3D0)
    c.add_text(f"## {title}")
    c.add_separator(divider=False)
    if message:
        c.add_text(message)
    return c
