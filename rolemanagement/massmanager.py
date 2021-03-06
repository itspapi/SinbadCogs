import discord
from redbot.core import checks, commands
from .converters import (
    RoleSyntaxConverter,
    ComplexActionConverter,
    ComplexSearchConverter,
    DynoSyntaxConverter,
)
import csv
import io


class MassManagementMixin:
    """
    Mass role operations
    """

    async def __before_invoke(self, ctx):  # ctx.guild.chunked is innaccurate.
        if ctx.guild:
            if any(m.joined_at is None for m in ctx.guild.members):
                await ctx.bot.request_offline_members(ctx.guild)

    @commands.guild_only()
    @checks.admin_or_permissions(manage_roles=True)
    @commands.group(name="massrole", autohelp=True, aliases=["mrole"])
    async def mrole(self, ctx: commands.Context):
        """
        Commands for mass role management
        """
        pass

    # start dyno mode

    @mrole.group(name="dynomode", autohelp=True)
    async def drole(self, ctx: commands.Context):
        """
        Provides syntax similar to dyno bots for ease of transition
        """
        pass

    @drole.command(name="bots")
    async def drole_bots(self, ctx: commands.Context, *, roles: DynoSyntaxConverter):
        """
        adds/removes roles to all bots.

        Roles should be comma seperated and preceded by a `+` or `-` indicating
        to give or remove

        You cannot add and remove the same role

        Example Usage:

        [p]massrole bots +RoleToGive, -RoleToRemove

        """
        give, remove = roles["+"], roles["-"]
        if not self.all_are_valid_roles(ctx, (give + remove)):
            return await ctx.send(
                "Either you or I don't have the required permissions "
                "or position in the hierarchy."
            )

        for member in ctx.guild.members:
            if member.bot:
                await self.update_roles_atomically(member, give=give, remove=remove)

        await ctx.tick()

    @drole.command(name="all")
    async def drole_all(self, ctx: commands.Context, *, roles: DynoSyntaxConverter):
        """
        adds/removes roles to all users.

        Roles should be comma seperated and preceded by a `+` or `-` indicating
        to give or remove

        You cannot add and remove the same role

        Example Usage:

        [p]massrole all +RoleToGive, -RoleToRemove
        """

        give, remove = roles["+"], roles["-"]
        if not self.all_are_valid_roles(ctx, (give + remove)):
            return await ctx.send(
                "Either you or I don't have the required permissions "
                "or position in the hierarchy."
            )

        for member in ctx.guild.members:
            await self.update_roles_atomically(
                member, give=roles["+"], remove=roles["-"]
            )

        await ctx.tick()

    @drole.command(name="humans")
    async def drole_humans(self, ctx: commands.Context, *, roles: DynoSyntaxConverter):
        """
        adds/removes roles to all humans.

        Roles should be comma seperated and preceded by a `+` or `-` indicating
        to give or remove

        You cannot add and remove the same role

        Example Usage:

        [p]massrole humans +RoleToGive, -RoleToRemove

        """
        give, remove = roles["+"], roles["-"]
        if not self.all_are_valid_roles(ctx, (give + remove)):
            return await ctx.send(
                "Either you or I don't have the required permissions "
                "or position in the hierarchy."
            )

        for member in ctx.guild.members:
            if not member.bot:
                await self.update_roles_atomically(
                    member, give=roles["+"], remove=roles["-"]
                )

        await ctx.tick()

    @drole.command(name="user")
    async def drole_user(
        self, ctx: commands.Context, user: discord.Member, *, roles: DynoSyntaxConverter
    ):
        """
        adds/removes roles to a user

        Roles should be comma seperated and preceded by a `+` or `-` indicating
        to give or remove

        You cannot add and remove the same role

        Example Usage:

        [p]massrole user Sinbad#0001 +RoleToGive, -RoleToRemove

        """
        give, remove = roles["+"], roles["-"]
        if not self.all_are_valid_roles(ctx, (give + remove)):
            return await ctx.send(
                "Either you or I don't have the required permissions "
                "or position in the hierarchy."
            )

        await self.update_roles_atomically(user, give=roles["+"], remove=roles["-"])

        await ctx.tick()

    @drole.command(name="in")
    async def drole_user_in(
        self, ctx: commands.Context, role: discord.Role, *, roles: DynoSyntaxConverter
    ):
        """
        adds/removes roles to all users with a specified role

        Roles should be comma seperated and preceded by a `+` or `-` indicating
        to give or remove

        You cannot add and remove the same role

        Example Usage:

        [p]massrole in "Red Team" +Champions, -Losers
        """

        give, remove = roles["+"], roles["-"]
        if not self.all_are_valid_roles(ctx, (give + remove)):
            return await ctx.send(
                "Either you or I don't have the required permissions "
                "or position in the hierarchy."
            )

        for member in role.members:
            await self.update_roles_atomically(
                member, give=roles["+"], remove=roles["-"]
            )

        await ctx.tick()

    # end dyno transitional stuff

    def search_filter(self, members: set, query: dict) -> set:
        """
        Reusable
        """

        if not query["everyone"]:

            if query["bots"]:
                members = {m for m in members if m.bot}
            elif query["humans"]:
                members = {m for m in members if not m.bot}

            for role in query["all"]:
                members &= set(role.members)
            for role in query["none"]:
                members -= set(role.members)

            if query["any"]:
                any_union = set()
                for role in query["any"]:
                    any_union |= set(role.members)
                members &= any_union

            if query["hasperm"]:
                perms = discord.Permissions()
                perms.update(**{x: True for x in query["hasperm"]})
                members = {m for m in members if m.guild_permissions >= perms}

            if query["anyperm"]:

                def has_any(mem):
                    for perm, value in iter(mem.guild_permissions):
                        if value and perm in query["anyperm"]:
                            return True
                    else:
                        return False

                members = {m for m in members if has_any(m)}

            if query["notperm"]:

                def has_none(mem):
                    for perm, value in iter(mem.guild_permissions):
                        if value and perm in query["notperm"]:
                            return False
                    else:
                        return True

                members = {m for m in members if has_none(m)}

        return members

    @mrole.command(name="user")
    async def mrole_user(
        self, ctx: commands.Context, user: discord.Member, *, roles: RoleSyntaxConverter
    ):
        """
        adds/removes roles to a user

        You cannot add and remove the same role

        Example Usage:

        [p]massrole user Sinbad#0001 --add RoleToGive "Role with spaces to give" 
        --remove RoleToRemove "some other role to remove" Somethirdrole

        For role operations based on role membership, permissions had, or whether someone is a bot
        (or even just add to/remove from all) see `[p]massrole search` and `[p]massrole modify` 
        """
        give, remove = roles["+"], roles["-"]
        if not self.all_are_valid_roles(ctx, (give + remove)):
            return await ctx.send(
                "Either you or I don't have the required permissions "
                "or position in the hierarchy."
            )

        await self.update_roles_atomically(user, give=roles["+"], remove=roles["-"])

        await ctx.tick()

    @mrole.command(name="search")
    async def mrole_search(
        self, ctx: commands.Context, *, query: ComplexSearchConverter
    ):
        """
        Searches for users with the specified role criteria

        --has-all roles
        --has-none roles
        --has-any roles
        --has-perm permissions
        --any-perm permissions
        --not-perm permissions
        --only-humans
        --only-bots
        --csv

        csv output will be used if output would exceed embed limits, or if flag is provided
        """

        members = set(ctx.guild.members)
        members = self.search_filter(members, query)

        if len(members) < 50 and not query["csv"]:

            def chunker(memberset, size=3):
                ret_str = ""
                for i, m in enumerate(memberset, 1):
                    ret_str += m.mention
                    if i % size == 0:
                        ret_str += "\n"
                    else:
                        ret_str += " "
                return ret_str

            description = chunker(members)
            color = ctx.guild.me.color if ctx.guild else discord.Embed.Empty
            embed = discord.Embed(description=description, color=color)
            await ctx.send(
                embed=embed, content=f"Search results for {ctx.author.mention}"
            )

        else:
            csvf = io.StringIO()
            fieldnames = [
                "ID",
                "Display Name",
                "Username#Discrim",
                "Joined Server",
                "Joined Discord",
            ]
            fmt = "%Y-%m-%d"
            writer = csv.DictWriter(csvf, fieldnames=fieldnames)
            writer.writeheader()
            for member in members:
                writer.writerow(
                    {
                        "ID": member.id,
                        "Display Name": member.display_name,
                        "Username#Discrim": str(member),
                        "Joined Server": member.joined_at.strftime(fmt),
                        "Joined Discord": member.created_at.strftime(fmt),
                    }
                )

            csvf.seek(0)
            data = io.BytesIO(csvf.read().encode())
            data.seek(0)
            await ctx.send(
                content=f"Data for {ctx.author.mention}",
                files=[discord.File(data, filename=f"{ctx.message.id}.csv")],
            )
            csvf.close()
            data.close()
            del csvf
            del data

    @mrole.command(name="modify")
    async def mrole_complex(
        self, ctx: commands.Context, *, query: ComplexActionConverter
    ):
        """
        Similar syntax to search, while applying/removing roles
        
        --has-all roles
        --has-none roles
        --has-any roles
        --has-perm permissions
        --any-perm permissions
        --not-perm permissions
        --add roles
        --remove roles
        --only-humans
        --only-bots
        --everyone
        """

        apply = query["add"] + query["remove"]
        if not self.all_are_valid_roles(ctx, *apply):
            return await ctx.send(
                "Either you or I don't have the required permissions "
                "or position in the hierarchy."
            )

        members = set(ctx.guild.members)
        members = self.search_filter(members, query)

        for member in members:
            await self.update_roles_atomically(
                member, give=query["add"], remove=query["remove"]
            )

        await ctx.tick()
