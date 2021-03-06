import pprint
import logging
import os
import collections
from enum import Enum, unique
from gensim import models
from gensim import corpora
from collections import defaultdict
from gensim import similarities
from gensim.test.utils import datapath
import pyLDAvis.gensim
# set up
@unique
class CorpList(Enum):
    Fangfang = 0
    Western = 1
    Chinese = 2
    AllNews = 3

logging.basicConfig(filename='gensim.log',
                    format="%(asctime)s:%(levelname)s:%(message)s",
                    level=logging.INFO)
pardir = os.path.abspath(os.path.join(os.path.dirname('CorpusTool.py'), os.path.pardir)) + '/'
corpPrefix_default = pardir + 'corpus_files/'

glbpath = 'ldamodel_all'   # total model
grp_paths = ['ldamodel_0', 'ldamodel_1', 'ldamodel_2', 'ldamodel_3', 'ldamodel_4']
grppath_0 = 'ldamodel_0'   # western  [BBC, DW, NTY, sputiknews]
grppath_1 = 'ldamodel_1'   # official [renmin, cnr, huanqiu]
grppath_2 = 'ldamodel_2'   # chinadaily
grppath_3 = 'ldamodel_3'   # fangfang diary
grppath_4 = 'ldamodel_4'   # chinese

class TopicAnalysisModel(object):
    """
    Tool for corpus analysis
    """
    def __init__(self, corpPrefix=corpPrefix_default):
        self.params = {}
        self.params['corpPrefix'] = corpPrefix
        self.params['corplist'] = ['BBC', 'chinadaily', 'DW', 'huanqiu', 'NTY', 'renmin', 'sputniknews', 'CNR']
        self.params['pglist'] =   [  19 ,      22     ,   1 ,     30   ,   56 ,    27   ,      30      ,  50 ]
        self.params['newssizelist'] = [] # definited by reading process
        # for global one
        self.glbcorpus = None
        self.corpdict = None
        self.bowcorpus = None
        self.num_topics = 5
        # for groups
        self.wstn_list = ['BBC', 'DW', 'NTY', 'sputiknews']
        self.wstn_sizes = []
        self.chn_list = ['chinadaily', 'huanqiu', 'renmin', 'CNR']
        self.chn_sizes = []
        self.grp_corpus = [[], [], [], [], []]
        self.grp_corpdict = [[], [], [], [], []]
        self.grp_bowcorpus = [[], [], [], [], []]

    def read_corpus(self, diary=False):
        """
        Method for reading all corpus files in corpus_files/..
        Setter for self.glbcorpus : list (len = number of total news in all news files)
        """
        if diary == False:
            glbcorpus = []
            grpcorpus = [[],[],[],[],[]]
            glbwords = 0
            glbarticles = 0
            print(">>> Start processing corpus files")
            for i in range(len(self.params['corplist'])):
                fpath = self.params['corpPrefix'] + self.params['corplist'][i] + '.txt'
                fin = open(fpath, 'r')
                # print('>>>> Start reading corpus file: ', fpath)
                # read file
                lines = fin.readlines()
                print('[' + self.params['corplist'][i] + ']' + ' article size: ', len(lines),
                      ', words: ', sum([len(line.split(' ')) for line in lines]))
                # data handle
                self.params['newssizelist'].append(len(lines))
                glbarticles += len(lines)
                glbwords += sum([len(line.split(' ')) for line in lines])
                glbcorpus += [line[:-1] for line in lines]
                # set group corpus
                if i in [0, 2, 4, 6]:
                    grpcorpus[0] += [line[:-1] for line in lines]
                    self.wstn_sizes.append(len(lines))
                if i in [3, 5, 7]:
                    grpcorpus[1] += [line[:-1] for line in lines]
                if i in [1]:
                    grpcorpus[2] += [line[:-1] for line in lines]
                if i in [1, 3, 5, 7]:
                    grpcorpus[4] += [line[:-1] for line in lines]
                    self.chn_sizes.append(len(lines))
            print('newssizelist:' ,self.params['newssizelist'])
            self.glbcorpus = [document.split(' ') for document in glbcorpus]
            for i in range(len(grp_paths)):
                if i != 3:
                    self.grp_corpus[i] = [document.split(' ') for document in grpcorpus[i]]
            return glbarticles, glbwords
        else:
            diarycorpus = []
            diarywords = 0
            diaryarticles = 0
            fpath = self.params['corpPrefix'] + 'fangfang.txt'
            fin = open(fpath, 'r')
            lines = fin.readlines()
            print('[fangfang]' + ' article size: ', len(lines),
                  ', words: ', sum([len(line.split(' ')) for line in lines]))
            diarywords += sum([len(line.split(' ')) for line in lines])
            diaryarticles += len(lines)
            diarycorpus += [line[:-1] for line in lines]
            self.grp_corpus[3] = [document.split(' ') for document in diarycorpus]
            return diaryarticles, diarywords

    def corpus2bow(self, corpus=None):
        print('>>> Start corpus -> bow process')
        if corpus == None:
            corpus = self.glbcorpus
        # word <-> id
        corpdictionary = corpora.Dictionary(corpus)
        # filter words with extreme frenquency
        self.corpdict = corpdictionary
        self.corpdict.filter_extremes(no_below=20, no_above=0.5)
        self.bowcorpus = [self.corpdict.doc2bow(doc) for doc in corpus]
        print('Number of unique tokens %d' % len(self.corpdict))
        print('Number of documents %d' % len(self.bowcorpus))
        for i in range(len(grp_paths)):
            dict = corpora.Dictionary(self.grp_corpus[i])
            self.grp_corpdict[i] = dict
            self.grp_corpdict[i].filter_extremes(no_below=20, no_above=0.5)
            self.grp_bowcorpus[i] = [self.grp_corpdict[i].doc2bow(doc) for doc in self.grp_corpus[i]]

    def LDA(self, corpdictionary=None, bowcorpus=None, num_topics=6, random_state=100, iterations=400, passes=20, alpha='auto', eta='auto',
            train_grp = True):
        if corpdictionary == None:
            corpdictionary = self.corpdict
        if bowcorpus == None:
            bowcorpus = self.bowcorpus
        # print('dic:', corpdictionary)
        temp = corpdictionary[0] # only to load dictionary≥
        id2word = corpdictionary.id2token
        print('tokens:', id2word)
        chunksize = len(bowcorpus)
        print(">>> Start LDA Modeling")
        LDAModel = models.LdaModel(
            corpus=bowcorpus,
            id2word=id2word,
            chunksize=chunksize,
            random_state=random_state,
            iterations=iterations,
            num_topics=num_topics,
            passes=passes,
            eval_every=None,
            alpha=alpha,
            eta=eta
        )
        print('########## Result global###########')
        temp_file = datapath('glbLDAmodel')
        print('save model', temp_file)
        LDAModel.save(temp_file)
        print('save completed')
        LDAModel.print_topics()
        top_topics = LDAModel.top_topics(bowcorpus)  # , num_words=20)

        # Average topic coherence is the sum of topic coherences of all topics, divided by the number of topics.
        avg_topic_coherence = sum([t[1] for t in top_topics]) / num_topics
        print('Average topic coherence: %.4f.' % avg_topic_coherence)
        pprint.pprint(top_topics)
        # visulization
        vis = pyLDAvis.gensim.prepare(LDAModel, bowcorpus, corpdictionary)
        pyLDAvis.save_html(vis, glbpath + '.html')

        if train_grp == True:
            for i in range(len(grp_paths)):
                corpdictionary = self.grp_corpdict[i]
                temp = corpdictionary[0]  # only to load dictionary
                id2word = corpdictionary.id2token
                bowcorpus = self.grp_bowcorpus[i]
                chunksize = len(bowcorpus)
                LDAModel = models.LdaModel(
                    corpus=bowcorpus,
                    id2word=id2word,
                    chunksize=chunksize,
                    random_state=random_state,
                    iterations=iterations,
                    num_topics=num_topics,
                    passes=passes,
                    eval_every=None,
                    alpha=alpha,
                    eta=eta
                )
                print('################Result group:', i+1)
                temp_file = datapath('LDA' + str(i) + 'model')
                LDAModel.save(temp_file)
                LDAModel.print_topics()
                top_topics = LDAModel.top_topics(bowcorpus)  # , num_words=20)
                # Average topic coherence is the sum of topic coherences of all topics, divided by the number of topics.
                avg_topic_coherence = sum([t[1] for t in top_topics]) / num_topics
                print('Average topic coherence: %.4f.' % avg_topic_coherence)
                pprint.pprint(top_topics)
                # visulization
                vis = pyLDAvis.gensim.prepare(LDAModel, bowcorpus, corpdictionary)
                pyLDAvis.save_html(vis, grp_paths[i] + '.html')

# case 0: all  1: western   2:china    3:fangfang
    def compare_data(self, model, case):
            corplist = []
            sizelist = []
            if case == 0:
                corplist = self.params['corplist']
                sizelist = self.params['newssizelist']
                # bowcorpus = self.bowcorpus
            elif case == 1:
                # corplist = self.wstn_list
                corplist = ['western']
                sizelist = [sum(self.wstn_sizes)]
                # bowcorpus = self.grp_bowcorpus[0]
            elif case == 2:
                # corplist = self.chn_list
                corplist = ['chinese']
                sizelist = [sum(self.chn_sizes)]
                # bowcorpus = self.grp_bowcorpus[4]
            elif case == 3:
                corplist = ['fangfang']
                sizelist = [60]
            papers = dict()
            if case == 0:
                st, ed = 0, 0
                for index, paper in enumerate(corplist):
                    ed += sizelist[index]
                    papers[paper] = self.bowcorpus[st:ed]
                    st = ed
            elif case == 1:
                papers['western'] = [self.corpdict.doc2bow(doc) for doc in self.grp_corpus[0]]
            elif case == 2:
                papers['chinese'] = [self.corpdict.doc2bow(doc) for doc in self.grp_corpus[4]]
            elif case == 3:
                papers['fangfang'] = [self.corpdict.doc2bow(doc) for doc in self.grp_corpus[3]]
                # result = model.top_topics(bowCorpus)
                # pprint.pprint(result)
            res = []
            print('corplist: ', corplist)
            for index, paper in enumerate(corplist):
                topicsSum = [0.0 for i in range(self.num_topics)]
                for result in model.get_document_topics(papers[paper]):
                    for (topic, value) in result:
                        topicsSum[topic] += value
                avgTopics = [value/sizelist[index] for value in topicsSum]
                res.append((paper, avgTopics))
                    # print(paper, avgTopics)
            return res
                # pprint.pprint(result)

if __name__ == '__main__':
    model = TopicAnalysisModel()
    model.read_corpus(diary=False)
    model.read_corpus(diary=True)
    model.corpus2bow()
    model.LDA(train_grp=True, num_topics=model.num_topics)
