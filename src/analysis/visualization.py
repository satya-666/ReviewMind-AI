"""Small static figures from measured data, with explicit absent-data handling."""
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR',str(Path(__file__).resolve().parents[2]/'.cache/matplotlib'))
os.environ.setdefault('XDG_CACHE_HOME',str(Path(__file__).resolve().parents[2]/'.cache'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np
import pandas as pd
from scripts.categorize import CATEGORIES
from .dataset_analysis import LANGUAGES

FIGURES = ['dataset_overview','category_distribution','category_rating_comparison',
 'category_language_distribution','rating_distribution','sentiment_distribution','rating_by_category',
 'language_distribution','language_by_category','language_rating_comparison',
 'review_length_distribution','review_length_by_category','common_review_terms',
 'reviews_per_product','product_review_coverage']

def plot_figures(frame,metrics,directory):
    directory = Path(directory); directory.mkdir(parents=True,exist_ok=True)
    available = {f.name for f in font_manager.fontManager.ttflist}
    fonts = [f for f in ['Noto Sans Devanagari','Devanagari Sangam MN','Nirmala UI','DejaVu Sans'] if f in available]
    plt.rcParams.update({'font.family':fonts or ['DejaVu Sans'],'font.size':10,'axes.spines.top':False,
                        'axes.spines.right':False,'figure.dpi':120,'savefig.dpi':160})
    paths = []
    context = f"Flipkart v1 • n={len(frame):,} retained reviews • product identities are exact-name proxies"
    def save(name,title,draw):
        fig,ax = plt.subplots(figsize=(11,6))
        ax.set_title(title,pad=14,fontweight='bold')
        if frame.empty:
            ax.text(.5,.5,'No review records available',ha='center',transform=ax.transAxes)
            ax.set_axis_off()
        else:
            draw(fig,ax)
        fig.text(.02,.015,context,fontsize=8,color='#555555')
        fig.tight_layout(rect=(0,.045,1,1))
        path = directory/(name+'.png'); fig.savefig(path,metadata={'Software':'ReviewMind AI Phase 2'}); plt.close(fig)
        paths.append(path.name)
    def bars(ax,values,xlabel='Reviews',ylabel=None):
        labels = [str(k).replace('_',' ') for k in values]
        ax.barh(labels,list(values.values()),color='#237A8A')
        ax.invert_yaxis(); ax.set_xlabel(xlabel)
        if ylabel: ax.set_ylabel(ylabel)
        ax.grid(axis='x',alpha=.2)
    def heat(ax,table,xlabel,ylabel):
        image = ax.imshow(table.to_numpy(dtype=float),aspect='auto',cmap='Blues')
        ax.set_xticks(range(len(table.columns)),[str(x).replace('_',' ') for x in table.columns],rotation=40,ha='right')
        ax.set_yticks(range(len(table.index)),[str(x).replace('_',' ') for x in table.index])
        ax.set_xlabel(xlabel); ax.set_ylabel(ylabel)
        for i in range(len(table.index)):
            for j in range(len(table.columns)):
                ax.text(j,i,str(int(table.iloc[i,j])),ha='center',va='center',fontsize=8,
                        color='white' if table.iloc[i,j]>table.to_numpy().max()*.55 else '#222222')
        ax.figure.colorbar(image,ax=ax,label='Reviews')
    cats = CATEGORIES[:-1]
    category_values = {k:metrics['categories'][k]['reviews'] for k in cats}
    save('dataset_overview','Dataset overview: retained split sizes',lambda f,a:bars(a,metrics['overview']['reviews_per_split']))
    save('category_distribution','Technology category coverage (zero means absent)',lambda f,a:bars(a,category_values))
    def means(ax,values,label):
        present = {k:v for k,v in values.items() if v is not None}
        bars(ax,present,label)
        ax.set_xlim(0,5)
    save('category_rating_comparison','Mean rating by represented category (descriptive only)',
         lambda f,a:means(a,{k:v['rating']['summary']['mean'] for k,v in metrics['categories'].items()},'Mean rating (1–5 stars)'))
    ct = pd.crosstab(frame['product_category'],frame['language']).reindex(index=cats,columns=LANGUAGES,fill_value=0)
    for name in ['category_language_distribution','language_by_category']:
        save(name,'Category × supplied language label counts',lambda f,a:heat(a,ct,'Weak language label','Category'))
    save('rating_distribution','Overall star-rating distribution',lambda f,a:bars(a,metrics['ratings']['distribution'],'Reviews','Stars'))
    save('sentiment_distribution','Rating-derived weak overall sentiment (not ground truth)',
         lambda f,a:bars(a,metrics['ratings']['weak_sentiment_counts']))
    rating_table = pd.crosstab(frame['product_category'],frame['rating']).reindex(index=cats,columns=[1,2,3,4,5],fill_value=0)
    save('rating_by_category','Category × star-rating counts',lambda f,a:heat(a,rating_table,'Stars','Category'))
    save('language_distribution','Supplied language labels: uncertainty retained',lambda f,a:bars(a,metrics['languages']['counts']))
    save('language_rating_comparison','Mean star rating by supplied language label',
         lambda f,a:means(a,{k:v['rating']['summary']['mean'] for k,v in metrics['languages']['by_language'].items()},'Mean rating (1–5 stars)'))
    words = frame['cleaned_text'].fillna('').str.split().str.len()
    def length_plot(fig,ax):
        chars = frame['cleaned_text'].fillna('').str.len()
        ax.hist(chars,bins=40,color='#237A8A',alpha=.8,label='Characters')
        ax.set_xlabel('Characters (full observed range)'); ax.set_ylabel('Reviews'); ax.set_yscale('log')
        ax.legend(); inset = ax.inset_axes([.58,.5,.36,.35])
        inset.hist(words,bins=30,color='#DA8945'); inset.set_title('Whitespace words',fontsize=9); inset.set_yscale('log')
    save('review_length_distribution','Review lengths (log review-count axis)',length_plot)
    def lengths_by_category(fig,ax):
        labels = [k for k in cats if frame['product_category'].eq(k).any()]
        ax.boxplot([words.loc[frame['product_category'].eq(k)] for k in labels],orientation='horizontal',tick_labels=[k.replace('_',' ') for k in labels],showfliers=False)
        ax.set_xlabel('Whitespace-separated words; outlier points hidden (full stats in JSON)')
    save('review_length_by_category','Review length by category',lengths_by_category)
    terms = {x['term']:x['review_document_frequency'] for x in metrics['text']['terms']['unigrams']}
    save('common_review_terms','Common terms (no stopword removal; not validated aspects)',lambda f,a:bars(a,terms,'Reviews containing term'))
    sizes = frame.groupby('product_group').size().sort_values(ascending=False)
    def product_plot(fig,ax):
        ax.bar(range(1,len(sizes)+1),sizes,color='#237A8A'); ax.set_xlabel('Product-name group rank (no product names disclosed)'); ax.set_ylabel('Reviews')
    save('reviews_per_product','Review concentration across product-name groups',product_plot)
    save('product_review_coverage','Product-name groups by evidence band',lambda f,a:bars(a,metrics['products']['coverage_bands'],'Product-name groups'))
    return paths
