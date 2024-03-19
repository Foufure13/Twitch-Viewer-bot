import os
import signal
import sys
import argparse
import time
import random
import requests
import datetime
from random import shuffle
from threading import Thread
from streamlink import Streamlink
from fake_useragent import UserAgent
from threading import Semaphore
from rich.console import Console
from rich.live import Live
from rich.prompt import Prompt
from rich.spinner import Spinner
from rich.table import Table
from rich.text import Text
import subprocess

console = Console()

# Session creating for request
ua = UserAgent()
session = Streamlink()
session.set_option("http-headers", {
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": ua.random,
    "Client-ID": "ewvlchtxgqq88ru9gmfp1gmyt6h2b93",
    "Referer": "https://www.google.com/"
})

class ViewerBot:
    def __init__(self, nb_of_threads, channel_name, proxy_file=None, proxy_imported=False):
        self.proxy_imported = proxy_imported
        self.proxy_file = proxy_file
        self.nb_of_threads = int(nb_of_threads)
        self.channel_name = channel_name
        self.request_count = 0
        self.all_proxies = []
        self.processes = []
        self.proxyrefreshed = False
        self.channel_url = "https://www.twitch.tv/" + self.channel_name
        self.thread_semaphore = Semaphore(int(nb_of_threads))
        self.active_threads = 0
        self.should_stop = False

    def get_proxies(self):
        if not self.proxyrefreshed:
            if self.proxy_file:
                try:
                    with open(self.proxy_file, 'r') as f:
                        lines = [line.strip() for line in f.readlines() if line.strip()]
                        self.proxyrefreshed = True
                        return lines
                except FileNotFoundError:
                    print(f"Proxy file {self.proxy_file} not found.")
                    sys.exit(1)
            else:
                try:
                    response = requests.get("https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all")
                    if response.status_code == 200:
                        lines = response.text.split("\n")
                        lines = [line.strip() for line in lines if line.strip()]
                        self.proxyrefreshed = True
                        return lines
                except Exception as e:
                    console.print("Limit of proxy retrieval reached. Retry later", style="bold red")
                    return []

    def get_url(self):
        url = ""
        try:
            streams = session.streams(self.channel_url)
            url = streams['audio_only'].url if 'audio_only' in streams else streams['worst'].url
        except Exception as e:
            pass
        return url

    def stop(self):
        console.print("[bold red]Bot has been stopped[/bold red]")
        self.should_stop = True

    def update_display(self):
        with Live(console=console, refresh_per_second=10) as live:
            while not self.should_stop:
                table = Table(show_header=False, show_edge=False)
                table.add_column(justify="right")
                table.add_column(justify="left")
                
                text = Text(f"Number of requests sent: {self.request_count}")
                text.stylize("bold magenta")
                table.add_row(text, Spinner("aesthetic"))
                
                active_threads_text = Text(f"Active threads: {self.active_threads}")
                active_threads_text.stylize("bold cyan")
                table.add_row(active_threads_text, Spinner("aesthetic"))
                
                live.update(table)

    def open_url(self, proxy_data):
        self.active_threads += 1
        try:
            headers = {'User-Agent': ua.random}
            current_index = self.all_proxies.index(proxy_data)

            if proxy_data['url'] == "":
                proxy_data['url'] = self.get_url()
            current_url = proxy_data['url']
            try:
                if time.time() - proxy_data['time'] >= random.randint(1, 5):
                    current_proxy = {"http": proxy_data['proxy'], "https": proxy_data['proxy']}
                    with requests.Session() as s:
                        s.head(current_url, proxies=current_proxy, headers=headers, timeout=10)
                        self.request_count += 1
                    proxy_data['time'] = time.time()
                    self.all_proxies[current_index] = proxy_data
            except:
                pass
        except KeyboardInterrupt:
            self.should_stop = True
        finally:
            self.active_threads -= 1
            self.thread_semaphore.release()

    def record_audio(self):
        output_directory = "record"
        os.makedirs(output_directory, exist_ok=True)
        
        # Définir le chemin du fichier de sortie dans le dossier "record"
        output_file_path = os.path.join(output_directory, "output_audio.mp3")
        
        console.print("[bold green]Début de l'enregistrement audio[/bold green]")
        stream_url = self.get_url()
        
        # Mettez à jour la commande ffmpeg pour utiliser le chemin du fichier de sortie
        command = ['ffmpeg', '-i', stream_url, '-t', '60', '-vn', '-acodec', 'libmp3lame', output_file_path]
        
        # Exécutez la commande ffmpeg
        subprocess.run(command)
        
        console.print(f"[bold green]Enregistrement audio terminé et sauvegardé en tant que '{output_file_path}'[/bold green]")

    def main(self):
        start = datetime.datetime.now()
        proxies = self.get_proxies()
        signal.signal(signal.SIGINT, lambda signal, frame: self.stop())

        self.display_thread = Thread(target=self.update_display)
        self.display_thread.daemon = True
        self.display_thread.start()

        record_thread = Thread(target=self.record_audio)
        record_thread.start()

        while not self.should_stop:
            elapsed_seconds = (datetime.datetime.now() - start).total_seconds()

            if not self.proxyrefreshed or elapsed_seconds >= 300:
                self.proxyrefreshed = False
                proxies = self.get_proxies()
                start = datetime.datetime.now()
                self.all_proxies = [{'proxy': p, 'time': time.time(), 'url': ""} for p in proxies]

            for _ in range(self.nb_of_threads):
                if self.thread_semaphore.acquire(blocking=False):
                    proxy_data = random.choice(self.all_proxies)
                    Thread(target=self.open_url, args=(proxy_data,), daemon=True).start()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-threads', type=int, help='Number of threads')
    parser.add_argument('-twitchname', type=str, help='Twitch channel name')
    parser.add_argument('-proxyfile', type=str, help='File containing list of proxies')
    args = parser.parse_args()

    nb_of_threads = args.threads if args.threads else 100
    channel_name = args.twitchname if args.twitchname else Prompt.ask("Enter the name of the Twitch channel", default="test_channel")
    proxy_file = args.proxyfile if args.proxyfile else None

    bot = ViewerBot(nb_of_threads=nb_of_threads, channel_name=channel_name, proxy_file=proxy_file)
    try:
        bot.main()
    except KeyboardInterrupt:
        bot.stop()
