import tkinter as tk
from tkinter import ttk, scrolledtext
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import threading
import webbrowser
from PIL import Image, ImageTk
from io import BytesIO
import re


class NewsApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Times of India - News Reader")
        self.root.geometry("1200x800")
        self.root.configure(bg='#f0f0f0')
        
        # Variables
        self.articles = []
        self.documents = []
        self.vectorizer = None
        self.vectors = None
        self.image_cache = {}
        self.image_refs = []  # Keep references to prevent garbage collection
        
        # Create UI
        self.create_widgets()
        
    def create_widgets(self):
        # Header
        header_frame = tk.Frame(self.root, bg='#1a237e', height=80)
        header_frame.pack(fill='x', padx=0, pady=0)
        header_frame.pack_propagate(False)
        
        tk.Label(header_frame, text="📰 TIMES OF INDIA", 
                font=('Arial', 20, 'bold'), 
                fg='white', bg='#1a237e').pack(pady=20)
        
        # Main content frame
        main_frame = tk.Frame(self.root, bg='#f0f0f0')
        main_frame.pack(fill='both', expand=True, padx=20, pady=10)
        
        # Control panel
        control_frame = tk.Frame(main_frame, bg='#f0f0f0')
        control_frame.pack(fill='x', pady=10)
        
        # Fetch News Button
        self.fetch_btn = tk.Button(control_frame, text="🔄 Fetch Latest News", 
                                   font=('Arial', 11, 'bold'),
                                   bg='#1a237e', fg='white',
                                   padx=20, pady=10,
                                   relief='flat', cursor='hand2',
                                   command=self.fetch_news_threaded)
        self.fetch_btn.pack(side='left', padx=5)
        
        # Separator
        tk.Label(control_frame, text="|", font=('Arial', 14), bg='#f0f0f0', fg='#ccc').pack(side='left', padx=15)
        
        # Search Query Entry
        tk.Label(control_frame, text="Search Query:", font=('Arial', 10), bg='#f0f0f0').pack(side='left', padx=(0, 5))
        self.query_var = tk.StringVar(value="latest important news today")
        self.query_entry = tk.Entry(control_frame, textvariable=self.query_var, 
                                   width=30, font=('Arial', 10))
        self.query_entry.pack(side='left', padx=5)
        
        # Search Button
        self.search_btn = tk.Button(control_frame, text="🔍 Search", 
                                   font=('Arial', 10, 'bold'),
                                   bg='#ff6f00', fg='white',
                                   padx=15, pady=8,
                                   relief='flat', cursor='hand2',
                                   command=self.search_news_threaded)
        self.search_btn.pack(side='left', padx=5)
        self.search_btn.config(state='disabled')
        
        # Status label
        self.status_label = tk.Label(main_frame, text="Ready", 
                                     font=('Arial', 9), bg='#f0f0f0', fg='#666')
        self.status_label.pack(anchor='w', pady=5)
        
        # Progress bar
        self.progress = ttk.Progressbar(main_frame, mode='indeterminate', length=200)
        self.progress.pack(anchor='w', pady=5)
        self.progress.pack_forget()
        
        # Canvas with scrollbar for news articles with images
        canvas_frame = tk.Frame(main_frame, bg='#f0f0f0')
        canvas_frame.pack(fill='both', expand=True, pady=10)
        
        self.canvas = tk.Canvas(canvas_frame, bg='#f0f0f0', highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = tk.Frame(self.canvas, bg='#f0f0f0')
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bind mouse wheel for scrolling
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # Store article widgets
        self.article_widgets = []
        
    def _on_mousewheel(self, event):
        self.canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
    def update_status(self, message, show_progress=False):
        self.status_label.config(text=message)
        if show_progress:
            self.progress.pack(anchor='w', pady=5)
            self.progress.start(10)
        else:
            self.progress.stop()
            self.progress.pack_forget()
    
    def fetch_image(self, url, size=(150, 100)):
        """Fetch and resize image"""
        try:
            if url in self.image_cache:
                return self.image_cache[url]
            
            response = requests.get(url, timeout=5)
            img = Image.open(BytesIO(response.content))
            
            # Resize image to fit beside news
            img.thumbnail(size, Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            
            self.image_cache[url] = photo
            return photo
        except:
            return None
    
    def get_article_image(self, article_link):
        """Extract image URL from article page"""
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            page = requests.get(article_link, headers=headers, timeout=10)
            soup = BeautifulSoup(page.text, "html.parser")
            
            # Try to get og:image
            og_image = soup.find("meta", property="og:image")
            if og_image and og_image.get("content"):
                return og_image.get("content")
            
            # Try to find image in article
            img_tag = soup.find("img", class_=re.compile(r"_img|article-image|main-image"))
            if img_tag and img_tag.get("src"):
                return urljoin(article_link, img_tag["src"])
            
            # Try to find any image in the article
            img_tag = soup.find("img")
            if img_tag and img_tag.get("src"):
                return urljoin(article_link, img_tag["src"])
            
            return None
        except:
            return None
    
    def create_article_widget(self, article, number):
        """Create a frame for each article with image and text"""
        # Main frame for this article
        article_frame = tk.Frame(self.scrollable_frame, bg='white', relief='solid', borderwidth=1)
        article_frame.pack(fill='x', pady=5, padx=5)
        
        # Inner frame for content
        content_frame = tk.Frame(article_frame, bg='white')
        content_frame.pack(fill='x', padx=10, pady=10)
        
        # Left side - Image
        image_frame = tk.Frame(content_frame, bg='white', width=160, height=120)
        image_frame.pack(side='left', padx=(0, 10))
        image_frame.pack_propagate(False)
        
        # Image label
        img_label = tk.Label(image_frame, bg='#f5f5f5', text="📷", font=('Arial', 24))
        img_label.pack(fill='both', expand=True)
        
        # Right side - Text content
        text_frame = tk.Frame(content_frame, bg='white')
        text_frame.pack(side='left', fill='both', expand=True)
        
        # Article number and title
        title_text = f"{number}. {article['title']}"
        title_label = tk.Label(text_frame, text=title_text, 
                              font=('Arial', 12, 'bold'), 
                              fg='#1a237e', bg='white',
                              wraplength=700, justify='left')
        title_label.pack(anchor='w', pady=(0, 5))
        
        # Bind click on title to open link
        title_label.bind('<Button-1>', lambda e, url=article['link']: webbrowser.open(url))
        title_label.bind('<Enter>', lambda e: title_label.config(cursor='hand2', fg='#1565c0'))
        title_label.bind('<Leave>', lambda e: title_label.config(cursor='', fg='#1a237e'))
        
        # Description
        text = article['text']
        sentences = text.split(".")
        short_news = []
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20:
                short_news.append(sentence)
            if len(short_news) == 3:
                break
        
        content = ". ".join(short_news) + "."
        desc_label = tk.Label(text_frame, text=content, 
                             font=('Arial', 10), 
                             fg='#333', bg='white',
                             wraplength=700, justify='left')
        desc_label.pack(anchor='w', pady=(0, 5))
        
        # Link
        link_label = tk.Label(text_frame, text=f"🔗 Read full article", 
                             font=('Arial', 9), 
                             fg='#1565c0', bg='white',
                             cursor='hand2')
        link_label.pack(anchor='w')
        link_label.bind('<Button-1>', lambda e, url=article['link']: webbrowser.open(url))
        
        # Store image label reference for later update
        article['img_label'] = img_label
        article['image_frame'] = image_frame
        
        # Try to load image in background
        if article.get('image'):
            self.load_image_for_article(article)
        
        # Store reference
        self.article_widgets.append(article_frame)
        
        return article_frame
    
    def load_image_for_article(self, article):
        """Load image for a specific article"""
        try:
            if article.get('image'):
                photo = self.fetch_image(article['image'])
                if photo:
                    img_label = article.get('img_label')
                    if img_label:
                        img_label.config(image=photo, text='')
                        img_label.image = photo
                        self.image_refs.append(photo)  # Keep reference
        except:
            pass
    
    def fetch_news_threaded(self):
        thread = threading.Thread(target=self.fetch_news)
        thread.daemon = True
        thread.start()
        
    def fetch_news(self):
        try:
            self.fetch_btn.config(state='disabled')
            self.search_btn.config(state='disabled')
            self.update_status("Fetching news from Times of India...", show_progress=True)
            
            # Clear existing widgets
            for widget in self.article_widgets:
                widget.destroy()
            self.article_widgets = []
            self.image_refs = []
            
            # Fetch articles
            url = "https://timesofindia.indiatimes.com/home/headlines"
            headers = {"User-Agent": "Mozilla/5.0"}
            
            page = requests.get(url, headers=headers, timeout=10)
            soup = BeautifulSoup(page.text, "html.parser")
            
            self.articles = []
            
            for a in soup.find_all("a", href=True):
                title = a.get_text(" ", strip=True)
                link = urljoin(url, a["href"])
                
                if "articleshow" in link and len(title) > 15:
                    if not any(x["link"] == link for x in self.articles):
                        self.articles.append({
                            "title": title,
                            "link": link,
                            "image": None,
                            "text": ""
                        })
            
            self.articles = self.articles[:10]
            
            if not self.articles:
                tk.Label(self.scrollable_frame, text="No articles found. Please try again.", 
                        font=('Arial', 12), bg='#f0f0f0', fg='red').pack(pady=20)
                return
            
            # Update status
            self.update_status(f"Found {len(self.articles)} articles. Fetching details...", show_progress=True)
            self.root.update()
            
            # Get descriptions and images
            headers = {"User-Agent": "Mozilla/5.0"}
            for article in self.articles:
                try:
                    page = requests.get(article["link"], headers=headers, timeout=10)
                    soup = BeautifulSoup(page.text, "html.parser")
                    
                    # Get description
                    description = soup.find("meta", property="og:description")
                    if description:
                        text = description.get("content", "").strip()
                    else:
                        paragraphs = soup.find_all("p")
                        text = " ".join(p.get_text(" ", strip=True) for p in paragraphs)
                    
                    article["text"] = text
                    
                    # Get image
                    image_url = self.get_article_image(article["link"])
                    if image_url:
                        article["image"] = image_url
                    
                except:
                    article["text"] = article["title"]
            
            # Remove empty articles
            self.articles = [a for a in self.articles if a["text"]]
            
            # Create documents for RAG
            self.documents = []
            for article in self.articles:
                document = article["title"] + " " + article["text"]
                self.documents.append(document)
            
            # Create TF-IDF vector database
            self.vectorizer = TfidfVectorizer(stop_words="english")
            self.vectors = self.vectorizer.fit_transform(self.documents)
            
            # Display articles with images
            for idx, article in enumerate(self.articles, 1):
                self.create_article_widget(article, idx)
                # Update UI to show images as they load
                self.root.update()
            
            self.update_status(f"✅ Loaded {len(self.articles)} articles successfully!", show_progress=False)
            self.search_btn.config(state='normal')
            
        except Exception as e:
            self.update_status(f"❌ Error: {str(e)}", show_progress=False)
            tk.Label(self.scrollable_frame, text=f"Error: {str(e)}", 
                    font=('Arial', 12), bg='#f0f0f0', fg='red').pack(pady=20)
        finally:
            self.fetch_btn.config(state='normal')
            self.progress.stop()
            self.progress.pack_forget()
            
    def search_news_threaded(self):
        thread = threading.Thread(target=self.search_news)
        thread.daemon = True
        thread.start()
        
    def search_news(self):
        try:
            self.search_btn.config(state='disabled')
            self.update_status("Searching...", show_progress=True)
            
            if not self.articles or self.vectorizer is None:
                self.update_status("Please fetch news first!", show_progress=False)
                return
            
            query = self.query_var.get().strip()
            if not query:
                query = "latest important news today"
            
            # Perform RAG retrieval
            query_vector = self.vectorizer.transform([query])
            scores = cosine_similarity(query_vector, self.vectors)[0]
            
            # Get top 5 news
            results = scores.argsort()[-5:][::-1]
            
            # Clear existing widgets
            for widget in self.article_widgets:
                widget.destroy()
            self.article_widgets = []
            
            # Display only top results
            for idx, i in enumerate(results, 1):
                article = self.articles[i]
                self.create_article_widget(article, idx)
                self.root.update()
            
            self.update_status(f"✅ Search completed! Found top {len(results)} relevant articles.", show_progress=False)
            
        except Exception as e:
            self.update_status(f"❌ Error: {str(e)}", show_progress=False)
        finally:
            self.search_btn.config(state='normal')
            self.progress.stop()
            self.progress.pack_forget()


def main():
    root = tk.Tk()
    app = NewsApp(root)
    root.mainloop()

if __name__ == "__main__":
    main()