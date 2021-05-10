#!/usr/bin/env python
# -*- coding: utf-8 -*-
import re
import ahocorasick
from copy import deepcopy
from xpinyin import Pinyin as py
import datetime
from collections import defaultdict


class EntityCorrect(object):
    """
    利用actrie树进行句子实体纠错和标准实体抽取，实体纠错：找商银行 -> 招商银行；实体标准化，招行 -> 招商银行
    func:句子实体纠错和标准实体抽取，支持下列两种数据格式
    attention：
    1.以(拼音：汉字)构建actrie树，会出现把实体同名误纠的问题
    2.以(汉字：汉字)构建actrie树，适用于同义词较确定的任务，但实体纠标准名局限性较大
    1.数据格式
    <标准名>
    招商银行
    方案一：以(拼音：汉字)构建actrie树，支持实体纠错，如:找商银行 -> 招商银行

    2.数据格式（之间以 /t 隔开，无表头<标准名>，<同义名>）
    <标准名>       <同义名>
    招商银行       招行
    方案一：以(拼音：汉字)构建actrie树，支持实体标准化，如:招行 -> 招商银行，找行 -> 招商银行，找商银行 -> 招商银行
    方案二：以(汉字：汉字)构建actrie树，支持实体标准化，如:招行 -> 招商银行

    :parameter

    """

    def __init__(self, synonym_path, use_pinyin=False, splitter_symbol="@@"):
        self.pinyin = py()
        self.splitter_symbol = splitter_symbol
        self.use_pinyin = use_pinyin
        self.synonym_dict, synonym_list = self._get_synonym(synonym_path, use_pinyin=self.use_pinyin)
        self.ac_synonym = self._build_actree(synonym_list)

    def _get_synonym(self, file_path, use_pinyin=True):
        """
        在txt文件中提取同义词，返回字典和列表
        :parameter file_path:文件路径，注意同义词表的同义词部分不能出现一对多的情况，例如 a:c, b:c，c指向a或者b冲突
        :return synonym_dict：同义词字典，{同义词名:标准名}
        :return wordlist：所有同义词
        """
        synonym_dict = {}
        word_all = []
        for line in open(file_path, "r", encoding='utf-8'):
            word_list = line.strip().split("\t")
            standard_word = word_list[0]
            for i in range(len(word_list)):
                word = word_list[i]
                if use_pinyin:
                    # 汉字转写拼音
                    seperate_pinyin = self.pinyin.get_pinyin(word_list[i], splitter=self.splitter_symbol)
                    word = seperate_pinyin
                synonym_dict[word] = standard_word
                if word not in word_all:
                    word_all.append(word)
        return synonym_dict, word_all

    def _build_actree(self, wordlist):
        """
        构建AC-trie树
        :parameter wordlist：所有同义词
        :return actree
        """
        actree = ahocorasick.Automaton()
        for index, word in enumerate(wordlist):
            actree.add_word(word, (index, word))
        actree.make_automaton()
        return actree

    def get_index(self, text, synonym, use_pinyin=True):
        """
        func：标记同义实体名在句子中的始末位置，便于替换成标准实体名
        :param text: 如果采用了汉字转拼音，那么text为拼音
        :param synonym: 同义实体名（中文或拼音）
        :return:
        start_index：同义实体名首位置
        end_index：同义实体名尾位置
        synonym：
        """
        if use_pinyin:
            word_len = len(synonym.split(self.splitter_symbol))
            start_index = len(text[:text.find(synonym)].split('@@')) - 1
            end_index = start_index + word_len
        else:
            word_len = len(synonym)
            start_index = text.find(synonym)
            end_index = start_index + word_len
        return start_index, end_index, synonym

    def run(self, text_raw):
        """
        func：句子实体纠错和标准实体抽取
        :parameter text_raw：未分词的用户输入
        :return
        update_text：纠错后的句子
        standard_synonym：(标准实体名，同义实体名)
        standard_namelist：抽取到并纠错完的实体列表
        """
        text_raw = re.sub('\s+', '', text_raw).strip()
        if self.use_pinyin:
            text_trans = self.pinyin.get_pinyin(text_raw, splitter=self.splitter_symbol)
        else:
            text_trans = text_raw

        match_synonym = []
        # 同义词AC-trie树查找输入中的同义词
        ac_match = self.ac_synonym.iter(text_trans)
        for end_index, (index, word_match) in ac_match:
            match_synonym.append(word_match)

        # 规则：将同一类型字串长度最长的标准名作为纠错转写的标准名
        del_index = []
        standard_namelist = []
        standard_synonym = []
        word_index_list = []
        for i in range(len(match_synonym)):
            word_index = self.get_index(text_trans, match_synonym[i], use_pinyin=self.use_pinyin)
            word_index_list.append(word_index)
            for j in range(len(match_synonym)):
                if i != j and match_synonym[i] in match_synonym[j]:
                    if i not in del_index:
                        del_index.append(i)
        for index in del_index:
            word_index_list.pop(index)

        # 返回最后结果
        update_text = text_raw
        for item in word_index_list:
            start_index, end_index, synonym = item[0], item[1], item[2]
            standard_name = self.synonym_dict[synonym]
            replace_word = text_raw[start_index:end_index]
            update_text = update_text.replace(replace_word, standard_name)
            result = (standard_name, synonym)
            standard_synonym.append(result)
            if standard_name not in standard_namelist:
                standard_namelist.append(standard_name)
        standard_synonym = list(set(standard_synonym))

        return update_text, standard_synonym, standard_namelist


if __name__=="__main__":
    text_1 = '找招行的张三'
    text_2 = '农行'
    text_3 = '去农行还是招行'
    synonym_path = './data/synonym.txt'
    EC = EntityCorrect(synonym_path, use_pinyin=True)
    update_text, standard_synonym, standard_namelist = EC.run(text_3)
    print("纠错后的句子为：{}".format(update_text))

    print("二元组结果为：{}".format(standard_synonym))

    print("纠错的实体为：{}".format(standard_namelist))

