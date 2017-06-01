import asyncio
import time
import threading
import arrow
import mistune
import re

from mitemite import Mite, Map, UI
from mitemite import Query as Q 
from mitemite import ElementBuilder as E
from mitemite import Materialize

import discord

class app():
	mite = Mite("views\\init.html", "Dissonance")
	miteui = UI(mite)
	materialize = Materialize(mite)
	client = discord.Client(max_messages=20000)

	active_channel = None
	active_server = None
	last_user = None
	last_message = None

	view_count = 0

	hot_panel = False

	@mite.onReady()
	def onready(event):
		Q("#init-card").show(300).execute(app.mite)
		print("Ready")

	@mite.onExit()
	def onexit(event):
		print("Exit Event Called")
		coro = app.client.logout()
		asyncio.run_coroutine_threadsafe(coro, app.client.loop)
		print("Exit Event Done")


	@mite.event("token-continue")
	def start_client(event):
		email = app.miteui.element("email").value
		password = app.miteui.element("password").value
		
		query = Q("#init-card").hide(300)
		query += Q("#init").hide()
		query += Q("#preloader").css("display", "flex")
		query.execute(app.mite)
		try:
			threading.Thread(target=app.complete_login).start()
			app.client.run(email, password)
		except:
			Q("#preloader").hide().execute(app.mite)
			Q("#init").show().execute(app.mite)
			Q("#init-card").show(300).execute(app.mite)
			app.materialize.toast("Invalid Credentials", 5000)


	@mite.event("hot-toggle")
	def toggle_hot(event):
		app.hot_panel = False if app.hot_panel else True

	@mite.event()
	def change_server(event, server_id):
		server = discord.utils.get(app.client.servers, id=server_id)
		app.active_server = server
		channel = [channel for channel in server.channels if channel.is_default][0].id
		app.change_channel(None, channel)

		query= Q("#server-title").text(server.name)
		query.execute(app.mite)

		app.populate_panel()

	def populate_panel():
		"""
		<li class="collection-item avatar">
          <img src="images/yuna.jpg" alt="" class="circle">
          <span class="title">Title</span>
          <p>First Line <br>
          </p>
        </li>
        """
		
		query = Q("#spm-members").prop("innerHTML", "")
		
		members = []
		for role in app.active_server.role_hierarchy:
			try:
				print("Processing: {}".format(role.name))
			except:
				pass

			role_member = [member for member in app.active_server.members if role in member.roles and member not in members]
			members.extend(role_member)

		items = ""
		for member in members:
			nick = member.nick if member.nick is not None else member.name
			nick = nick.replace("`", "")
			item = E("li").c("collection-item avatar grey darken-3").text(
						E("img").c("circle").src(member.avatar_url) +
						E("span").c("title").style("color: rgb({}, {}, {})".format(member.colour.r, member.colour.g, member.colour.b)).text(nick) +
						E("p").text("@{}:{}".format(member.name.replace("`", ""), member.status))
					)
			items += item.html

		query += Q("#spm-members").append(items.replace("`", "&grave;"))
		query.execute(app.mite)

	@mite.event()
	def change_channel(event, channel_id):
		app.last_user = None
		app.last_message = None
		app.active_channel = discord.utils.get(app.active_server.channels, id=channel_id)
		print("channel_id: {}".format(channel_id))

		# clears the channel list
		query = Q("#server-channels").text("")
		query += Q("#server-chatarea").text("")

		sorted_channels = []
		end_sort = False
		position = 0
		while not end_sort:
			end_sort = True
			for channel in app.active_server.channels:
				if channel.position == position:
					end_sort = False
					sorted_channels.append(channel)
					position += 1



		channels = ""
		for channel in sorted_channels:
			item_style = "grey darken-4 white-text"
			if channel == app.active_channel:
				item_style = "grey darken-4 white-text active-channel"
			channel_item = E("a").href("#").id(channel.id).c("collection-item {}".format(item_style)).text("#{}".format(channel.name))
			channel_item.onclick(Q.event_compile(app.change_channel, [channel.id]))
			channels += channel_item.html

		query += Q("#server-channels").append(channels)


		chat_box = E("form").id("server-chatbox").c("col s12").text(
						E("div").c("row").text(
							E("div").c("input-field col s12").text(
								E("textarea").id("txt-chatbox").c("white-text materialize-textarea").html +
								E("label")._for("server-chatbox").text("Send message to #{}".format(app.active_channel.name)).html
								)
							)
						)

		query += Q("#server-chatbox-container").prop("innerHTML", chat_box)
		query.execute(app.mite)

		js = """$('#txt-chatbox').keypress(function(e){
				    if(e.which == 13){
				    	send_message($('#txt-chatbox').val())
				        return false;
				    }
				});"""

		app.mite.xj(js)
		app.view_count = 0

		messages = [message for message in app.client.messages if message.channel == app.active_channel]
		messages = messages[0:100] if len(messages) > 100 else messages
		master_message = ""
		for message in messages:
			master_message += app.generate_message_cluster(message, "#server-chatarea", "flex").html

		Q("#server-chatarea").append(master_message).execute(app.mite)


	@mite.event()
	def refresh_server_list(event):
		Q("server-list-div").text("").execute(app.mite)
		for server in app.client.servers:
			try:
				if server.icon_url == "":
					text = E("span").text(server.name[0].upper())
				else:
					text = E("img").c("responsive-img circle tooltipped").data_position("top").data_tooltip(server.name).src(server.icon_url)
				server_tab = E("a",
								c="draggable-element",
								href="#",
								text = text,
								onclick = Q.event_compile(app.change_server, [server.id]))

				Q("#server-list-div").append(server_tab).execute(app.mite)
			except:
				pass

		query = Q(".tooltipped").tooltip({"delay": 50})
		query += Q(".draggable-element").arrangeable()
		query.execute(app.mite)


	@mite.event()
	def send_message(event, message):
		Q('#txt-chatbox').val("").execute(app.mite)
		coro = app.client.send_message(app.active_channel, message)
		coro_thread = asyncio.run_coroutine_threadsafe(coro, app.client.loop)
		coro_thread.result()


	def complete_login():
		while not app.client.is_logged_in and len(app.client.servers) == 0:
			time.sleep(5)


		app.materialize.toast("Logged in!")
		Q("#preloader").hide().execute(app.mite)
		Q("#app-container").show().execute(app.mite)
		app.refresh_server_list(None)


	@client.event
	async def on_message_delete(message):
		if message.channel == app.active_channel:
			query = Q("#{}".format(message.id)).attr("class", "message-content red-text tooltipped")
			query.attr("data-tooltip", "This message has been deleted.")
			query.execute(app.mite)
			Q(".tooltipped").tooltip({"delay": 50}).execute(app.mite)

	@client.event
	async def on_message_edit(old, new):
		if old.channel == app.active_channel:
			query = Q("#{}".format(old.id)).attr("class", "message-content blue-text tooltipped")
			query.attr("data-tooltip", "Old: {}".format(old.content))
			query.html(app.generate_message_content(new))
			query.execute(app.mite)
			Q(".tooltipped").tooltip({"delay": 50}).execute(app.mite)


	@client.event
	async def on_message(message):
		if message.channel == app.active_channel:
			print("message event called from {}".format(message.author.name))
			#Q("#server-chatarea").append("<strong>{}</strong>: {}<br>".format(message.author.name, message.content)).execute(app.mite)
			app.generate_message(message)
		else:
			print("message event from {}".format(message.author.name))
			if app.hot_panel and message.server == app.active_server:
				app.generate_message(message, False, "#serverpanel-hotstuff", "prepend")


	def generate_message_content(message):
		# Emoji parsing
		print(message.attachments)
		content = message.clean_content
		result_count = 1
		while result_count > 0:
			result = re.search("(<:(\w+):(\d+)>)", content)
			if result is None:
				result_count = 0
			elif len(result.groups()) != 0:
				content = content.replace(result.groups()[0], '<span><img draggable="false" class="emoji jumboable tooltipped" data-tooltip=":{}:" src="https://cdn.discordapp.com/emojis/{}.png"><span>'.format(result.groups()[1],result.groups()[2]))

		if len(message.attachments) > 0:
			if message.attachments[0]["filename"].split(".").pop() in [".jpg", ".jpeg", ".png", ".gif", ".webp"]:
				content += E("img").id(message.attachments[0]["id"]).c("attachment").src(message.attachments[0]["url"])

		content = mistune.markdown(content, escape=False)
		content = content.replace("`", "&‌grave;")
		return content


	def generate_message_cluster(message, to="", display="none"):
		content = app.generate_message_content(message)

		if app.last_message is not None:
			if app.last_user == message.author:
				# append it here
				id = app.last_message.get("id")
				Q("#{} .right-panel".format(app.last_message.get("id"))).append(E("span").id(message.id).c("message-content").text(content)).execute(app.mite)
				Q("#server-chatarea").prop("scrollTop", Q("#server-chatarea").prop("scrollHeight")).execute(app.mite)
				# breaks process here.
				return None
		try:
			if (message.author.colour.r, message.author.colour.g, message.author.colour.b) != (0, 0, 0):
				username = E("span").style("color: rgb({}, {}, {})".format(
					message.author.colour.r, message.author.colour.g, message.author.colour.b )).text(message.author.name)
			else:
				username = E("span").style("color: rgb({}, {}, {})".format(200, 200, 200)).text(message.author.name)
		except:
			username = E("span").style("color: rgb({}, {}, {})".format(200, 200, 200)).text(message.author.name)


		if to == "#serverpanel-hotstuff":
			time = "{} in #{}".format(arrow.now().format("hh:mm A"), message.channel.name)
			time = E("span").c("time tooltipped").text(time).data_tooltip(message.server.name)
		else:
			time = "{}".format(arrow.now().format("hh:mm A"))
			time = E("span").c("time tooltipped").text(E("p").text(time))
		"""
		new_message = E("div", id="msg-cluster-{}".format(message.id),
								c="msg-cluster",
								style="display: {};".format(display),
								text=E("div").c("left-panel").text(
										E("img").c("responsive-img").src(message.author.avatar_url)
										).html +
									 E("div").c("right-panel white-text").text(
									 	E("span").c("message-span").text( 
									 			username.html +
									 			time.html
									 		).html +
									 	E("span").id(message.id).c("message-content").text(content).html
									 	).html
								)
		"""
		new_message = E("div").id("msg-cluster-{}".format(message.id))
		new_message._class("msg-cluster")
		new_message.style("display: {};".format(display))
		new_message.text(
			E("div").c("left-panel").text(
				E("img").c("responsive-img").src(message.author.avatar_url)) +
			E("div").c("right-panel white-text").text(
				E("span").c("message-span").text(username + time) +
			 	E("span").id(message.id).c("message-content").text(content))
			)

		
		new_message = E("div").id("cluster-container-"+message.id).c("cluster-container").text(new_message)

		return new_message




	def generate_message(message, fast=False, to="#server-chatarea", where="append"):
		
		new_message = app.generate_message_cluster(message, to)

		# query = Q("#server-chatarea").append(new_message)
		if where == "append":
			query = Q(to).append(new_message)
		else:
			query = Q(to).prepend(new_message)


		
		if where == "append":
			query += Q("#msg-cluster-{}".format(message.id)).show().css('display', 'flex')
			if fast:
				query += Q("#server-chatarea").animate({
						  "scrollTop": Q("#server-chatarea").prop("scrollHeight")
						}, 0);
			else:
				query += Q("#server-chatarea").animate({
						  "scrollTop": Q("#server-chatarea").prop("scrollHeight")
						}, 1000);
		else:
			if fast:
				query += Q("#msg-cluster-{}".format(message.id)).slideUp(500).css('display', 'flex')
			else:
				query += Q("#msg-cluster-{}".format(message.id)).show(0).css('display', 'flex')
		
		if app.view_count > 200:
			query += Q("{} div".format(to)).first().remove();

		app.view_count += 1
		query += Q(".tooltipped").tooltip({"delay": 50})
		query.execute(app.mite)

		app.last_message = new_message
		app.last_user = message.author






app.mite.jObject(app)
app.mite.start()