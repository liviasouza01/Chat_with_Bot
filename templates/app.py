import datetime
from os import environ
import flask
import redis
import openai

app = flask.Flask("labex-sse-chat")
app.secret_key = "labex"
app.config["DEBUG"] = True
r = redis.StrictRedis()

openai_api_key= environ.get("OPENAI_KEY")

conversation_history = {}

#Verifica se o usuário está logado. Se não estiver, redireciona para a página de login
@app.route("/")
def home():
    if "user" not in flask.session:
        return flask.redirect("/login")
    user = flask.session["user"]
    return flask.render_template("index.html", user=user)

#Envia msg para o Redis e enviada pro cliente por Server Sent Events(SSE)
def event_stream():
    pubsub = r.pubsub()
    pubsub.subscribe("chat")
    for message in pubsub.listen():
        data = message["data"]
        if isinstance(data, bytes):
            yield "data: {}\n\n".format(data.decode())

@app.route("/login", methods=["GET", "POST"])
def login():
    if flask.request.method == "POST":
        flask.session["user"] = flask.request.form["user"]
        return flask.redirect("/")
    return flask.render_template("login.html")

@app.route("/post", methods=["POST"])
def post():
    message = flask.request.form["message"]
    user = flask.session.get("user", "anonymous")
    now = datetime.datetime.now().replace(microsecond=0).time() #horario da mensagem

    if user not in conversation_history:
        conversation_history[user] = []

    conversation_history[user].append({"role": "user", "content": message})

    #Publica a msg do usuário no Redis
    r.publish("chat", "[{}] {}: {}\n".format(now.isoformat(), user, message))
    
    try:
        #Chama a API pra obter uma resposta do bot
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=conversation_history[user]  # Envia o histórico de mensagens
        )
        
        bot_message = response["choices"][0]["message"]["content"]
        #Add a resposta do bot no histórico
        conversation_history[user].append({"role": "assistant", "content": bot_message})
        
        r.publish("chat", "[{}] Cesar: {}\n".format(now.isoformat(), bot_message))
    
    except Exception as e:
        print("Error:", e)  #Erro?

    return flask.Response(status=204)

#Frontend mostra as msgs em tempo real
@app.route("/stream")
def stream():
    return flask.Response(event_stream(), mimetype="text/event-stream")

if __name__ == "__main__":
    app.run()
