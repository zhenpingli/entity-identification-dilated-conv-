# # encoding = utf-8
# import numpy as np
# import tensorflow as tf
# from tensorflow.contrib.crf import crf_log_likelihood
# from tensorflow.contrib.crf import viterbi_decode
# from tensorflow.contrib.layers.python.layers import initializers
#
#
# from data_utils import create_input, iobes_iob,iob_iobes
#
#
# class Model(object):
#     # ��ʼ��ģ�Ͳ���
#     def __init__(self, config):
#         # ��init�ж��������������ѵ��ģ�飬����������Ĵ���Ż�����ѡ��
#
#         self.config = config
#
#         self.lr = config["lr"]
#         self.char_dim = config["char_dim"]
#         self.lstm_dim = config["lstm_dim"]
#         self.seg_dim = config["seg_dim"]
#
#         self.num_tags = config["num_tags"]
#         self.num_chars = config["num_chars"]  # ������������
#         self.num_segs = 4
#
#         self.global_step = tf.Variable(0, trainable=False)
#         self.best_dev_f1 = tf.Variable(0.0, trainable=False)
#         self.best_test_f1 = tf.Variable(0.0, trainable=False)
#         self.initializer = initializers.xavier_initializer()
#
#         # add placeholders for the model
#
#         self.char_inputs = tf.placeholder(dtype=tf.int32,
#                                           shape=[None, None],
#                                           name="ChatInputs")
#         self.seg_inputs = tf.placeholder(dtype=tf.int32,
#                                          shape=[None, None],
#                                          name="SegInputs")
#
#         self.targets = tf.placeholder(dtype=tf.int32,
#                                       shape=[None, None],
#                                       name="Targets")
#         # dropout keep prob
#         self.dropout = tf.placeholder(dtype=tf.float32,
#                                       name="Dropout")
#
#         used = tf.sign(tf.abs(self.char_inputs))
#         length = tf.reduce_sum(used, reduction_indices=1)
#         self.lengths = tf.cast(length, tf.int32)
#         self.batch_size = tf.shape(self.char_inputs)[0]
#         self.num_steps = tf.shape(self.char_inputs)[-1]
#
#         # Add model type by crownpku bilstm or idcnn
#         self.model_type = config['model_type']
#         # parameters for idcnn
#         self.layers = [
#             {
#                 'dilation': 1
#             },
#             {
#                 'dilation': 1
#             },
#             {
#                 'dilation': 2
#             },
#         ]
#         self.filter_width = 3
#         self.num_filter = self.lstm_dim
#         self.embedding_dim = self.char_dim + self.seg_dim
#         self.repeat_times = 4
#         self.cnn_output_width = 0
#
#         # embeddings for chinese character and segmentation representation
#         embedding = self.embedding_layer(self.char_inputs, self.seg_inputs, config)
#         # �ô��벻ִ�У�
#         if self.model_type == 'bilstm':
#             # apply dropout before feed to lstm layer
#             model_inputs = tf.nn.dropout(embedding, self.dropout)
#
#             # bi-directional lstm layer
#             model_outputs = self.biLSTM_layer(model_inputs, self.lstm_dim, self.lengths)
#
#             # logits for tags
#             self.logits = self.project_layer_bilstm(model_outputs)
#         # ִ�пն�����������
#         elif self.model_type == 'idcnn':
#             # apply dropout before feed to idcnn layer
#             model_inputs = tf.nn.dropout(embedding, self.dropout)
#
#             # ldcnn layer
#             model_outputs = self.IDCNN_layer(model_inputs)
#
#             # logits for tags
#             self.logits = self.project_layer_idcnn(model_outputs)
#
#         else:
#             raise KeyError
#
#         # loss of the model
#         # run_step����ִ�е�self.loss
#         self.loss = self.loss_layer(self.logits, self.lengths)
#         # ������ѡ����ʵ�optimizer����
#         with tf.variable_scope("optimizer"):
#             optimizer = self.config["optimizer"]
#             if optimizer == "sgd":
#                 self.opt = tf.train.GradientDescentOptimizer(self.lr)
#             elif optimizer == "adam":
#                 self.opt = tf.train.AdamOptimizer(self.lr)
#             elif optimizer == "adgrad":
#                 self.opt = tf.train.AdagradOptimizer(self.lr)
#             else:
#                 raise KeyError
#
#             # apply grad clip to avoid gradient explosion
#             grads_vars = self.opt.compute_gradients(self.loss)
#             # �����ݶȹ�����
#             capped_grads_vars = [[tf.clip_by_value(g, -self.config["clip"], self.config["clip"]), v]
#                                  for g, v in grads_vars]
#             self.train_op = self.opt.apply_gradients(capped_grads_vars, self.global_step)
#
#         # saver of the model
#         # ����ģ��
#         self.saver = tf.train.Saver(tf.global_variables(), max_to_keep=5)
#
#     def embedding_layer(self, char_inputs, seg_inputs, config, name=None):
#         """
#         :param char_inputs: one-hot encoding of sentence
#         :param seg_inputs: segmentation feature
#         :param config: wither use segmentation feature
#         :return: [1, num_steps, embedding size],
#         """
#         # ��:3 Ѫ:22 ��:23 ��:24 ��:3 Ѫ:22 ѹ:25 char_inputs=[3,22,23,24,3,22,25]
#         # ��Ѫ�� �� ��Ѫѹ seg_inputs ��Ѫ��=[1,2,3] ��=[0] ��Ѫѹ=[1,2,3]  seg_inputs=[1,2,3,0,1,2,3]
#         embedding = []
#         self.char_inputs_test = char_inputs
#         self.seg_inputs_test = seg_inputs
#         with tf.variable_scope("char_embedding" if not name else name), tf.device('/GPU:0'):
#             # ����ʹ��һ����������������ַ�������ʾ�ֵ�embedding���򻯴���
#             self.char_lookup = tf.get_variable(
#                 name="char_embedding",
#                 shape=[self.num_chars, self.char_dim],
#                 initializer=self.initializer)
#             # ����char_inputs='��' ��Ӧ���ֵ������/���/valueΪ��8
#             # self.char_lookup=[X(ÿ�仰�ĳ���)*100]��������char_inputs�ֶ�Ӧ���ֵ������/���/key=[1]
#             embedding.append(tf.nn.embedding_lookup(self.char_lookup, char_inputs))
#             # self.embedding1.append(tf.nn.embedding_lookup(self.char_lookup, char_inputs))
#             # �����char_inputs���������䣬����self.char_inputs = tf.placeholder���
#
#             # ����������ǽ�seg_inputs��embedding
#             if config["seg_dim"]:
#                 with tf.variable_scope("seg_embedding"), tf.device('/GPU:0'):
#                     self.seg_lookup = tf.get_variable(
#                         name="seg_embedding",
#                         # shape=[4*20]
#                         shape=[self.num_segs, self.seg_dim],
#                         initializer=self.initializer)
#                     embedding.append(tf.nn.embedding_lookup(self.seg_lookup, seg_inputs))
#             # ������ϲ�embedding
#             embed = tf.concat(embedding, axis=-1)
#         self.embed_test = embed
#         self.embedding_test = embedding
#         return embed
#
#     # IDCNN layer
#     def IDCNN_layer(self, model_inputs,
#                     name=None):
#         """
#         :param idcnn_inputs: [batch_size, num_steps, emb_size]
#         :return: [batch_size, num_steps, cnn_output_width]
#         """
#         # tf.expand_dims����tensor�в���һ��ά�ȣ�����λ�þ��ǲ���������λ�ã�ά�ȴ�0��ʼ����
#         model_inputs = tf.expand_dims(model_inputs, 1)
#         # ��������������ڷ��ص�sees���ӡ�ģ���û��ʵ������
#         self.model_inputs_test = model_inputs
#         reuse = False
#         if self.dropout == 1.0:
#             reuse = True
#         with tf.variable_scope("idcnn" if not name else name):
#             # shape=[1*3*120*100]
#             shape = [1, self.filter_width, self.embedding_dim,
#                      self.num_filter]
#             print(shape)
#             filter_weights = tf.get_variable(
#                 "idcnn_filter",
#                 shape=[1, self.filter_width, self.embedding_dim,
#                        self.num_filter],
#                 initializer=self.initializer)
#
#             """
#             shape of input = [batch, in_height, in_width, in_channels]
#             shape of filter = [filter_height, filter_width, in_channels, out_channels]
#             """
#             # �ڴ˴�ִ�������ľ���������
#             layerInput = tf.nn.conv2d(model_inputs,
#                                       filter_weights,
#                                       strides=[1, 1, 1, 1],
#                                       padding="SAME",
#                                       name="init_layer", use_cudnn_on_gpu=True)
#             # �����self.layerInput_testҲ��Ϊ��sees.run���ӡ����
#             self.layerInput_test = layerInput
#             finalOutFromLayers = []
#
#             totalWidthForLastDim = 0
#             for j in range(self.repeat_times):
#                 for i in range(len(self.layers)):
#                     # 1,1,2
#                     dilation = self.layers[i]['dilation']
#                     isLast = True if i == (len(self.layers) - 1) else False
#                     with tf.variable_scope("atrous-conv-layer-%d" % i,
#                                            reuse=True
#                                            if (reuse or j > 0) else False):
#                         # w �����˵ĸ߶ȣ������˵Ŀ��ȣ�ͼ��ͨ�����������˸���
#                         # �����ﶨ��ն�������Ҫ�Ĳ���
#                         w = tf.get_variable(
#                             "filterW",
#                             shape=[1, self.filter_width, self.num_filter,
#                                    self.num_filter],
#                             initializer=tf.contrib.layers.xavier_initializer())
#                         if j == 1 and i == 1:
#                             self.w_test_1 = w
#                         if j == 2 and i == 1:
#                             self.w_test_2 = w
#                         b = tf.get_variable("filterB", shape=[self.num_filter])
#                         # tf.nn.atrous_conv2d(value,filters,rate,padding,name=None��
#                         # ��ȥname��������ָ���ò�����name���뷽���йص�һ���ĸ�������
#                         # value��
#                         # ָ��Ҫ������������ͼ��Ҫ����һ��4άTensor������[batch, height, width, channels]������shape�����庬����[ѵ��ʱһ��batch��ͼƬ����, ͼƬ�߶�, ͼƬ����, ͼ��ͨ����]
#                         # filters��
#                         # �൱��CNN�еľ����ˣ�Ҫ����һ��4άTensor������[filter_height, filter_width, channels, out_channels]������shape�����庬����[�����˵ĸ߶ȣ������˵Ŀ��ȣ�ͼ��ͨ�����������˸���]��ͬ���������άchannels�����ǲ���value�ĵ���ά
#                         # rate��
#                         # Ҫ����һ��int�͵������������ľ�������Ӧ�û���stride���������˵Ļ��������������ǿն�������û��stride�����ģ�
#                         # ��һ������Ҫע�⡣ȡ����֮����ʹ�����µ�rate��������ôrate������ʲô���أ�������Ϊ����������
#                         # ͼ���Ͼ���ʱ�Ĳ�����������������Ϊ�����˵��д����ˣ�rate-1�������ġ�0����
#                         # ��ԭ���ľ����˲���˺ܶࡰ������������������ʱ���൱�ڶ�ԭͼ��Ĳ����������ˡ�
#                         # ������ô��ã����Կ����������ϸ����������ʱ���Ǻ����׵ó�rate=1ʱ����û��0���룬
#                         # ��ʱ��������ͱ������ͨ������
#                         # padding��
#                         # string���͵�����ֻ���ǡ�SAME��,��VALID������֮һ�����ֵ�����˲�ͬ��Ե��䷽ʽ��
#                         # ok�����ˣ������û�в����ˣ������е�С�������ǡ�stride�������ء���ʵ��������Ѿ�Ĭ����stride=1��Ҳ���ǻ��������޷��ı䣬�̶�Ϊ1��
#                         # �������һ��Tensor����䷽ʽΪ��VALID��ʱ������[batch,height-2*(filter_width-1),width-2*(filter_height-1),out_channels]��Tensor����䷽ʽΪ��SAME��ʱ������[batch, height, width, out_channels]��Tensor����������ô�ó����ģ��Ȳ���������ͨ��һ�γ����������ʾһ�¿ն�������
#                         conv = tf.nn.atrous_conv2d(layerInput,
#                                                    w,
#                                                    rate=dilation,
#                                                    padding="SAME")
#                         self.conv_test = conv
#                         conv = tf.nn.bias_add(conv, b)
#                         conv = tf.nn.relu(conv)
#                         if isLast:
#                             finalOutFromLayers.append(conv)
#                             totalWidthForLastDim += self.num_filter
#                         layerInput = conv
#             finalOut = tf.concat(axis=3, values=finalOutFromLayers)
#             keepProb = 1.0 if reuse else 0.5
#             finalOut = tf.nn.dropout(finalOut, keepProb)
#             # Removes dimensions of size 1 from the shape of a tensor.
#             # ��tensor��ɾ�����д�С��1��ά��
#
#             # Given a tensor input, this operation returns a tensor of the same type with all dimensions of size 1 removed. If you don��t want to remove all size 1 dimensions, you can remove specific size 1 dimensions by specifying squeeze_dims.
#
#             # �����������룬�˲���������ͬ���͵���������ɾ�����гߴ�Ϊ1�ĳߴ硣 �������ɾ�����гߴ�1�ߴ磬����ͨ��ָ��squeeze_dims��ɾ���ض��ߴ�1�ߴ硣
#             finalOut = tf.squeeze(finalOut, [1])
#             finalOut = tf.reshape(finalOut, [-1, totalWidthForLastDim])
#             self.cnn_output_width = totalWidthForLastDim
#             return finalOut
#
#     def project_layer_bilstm(self, lstm_outputs, name=None):
#         """
#         hidden layer between lstm layer and logits
#         :param lstm_outputs: [batch_size, num_steps, emb_size]
#         :return: [batch_size, num_steps, num_tags]
#         """
#         with tf.variable_scope("project" if not name else name):
#             with tf.variable_scope("hidden"):
#                 W = tf.get_variable("W", shape=[self.lstm_dim * 2, self.lstm_dim],
#                                     dtype=tf.float32, initializer=self.initializer)
#
#                 b = tf.get_variable("b", shape=[self.lstm_dim], dtype=tf.float32,
#                                     initializer=tf.zeros_initializer())
#                 output = tf.reshape(lstm_outputs, shape=[-1, self.lstm_dim * 2])
#                 hidden = tf.tanh(tf.nn.xw_plus_b(output, W, b))
#
#             # project to score of tags
#             with tf.variable_scope("logits"):
#                 W = tf.get_variable("W", shape=[self.lstm_dim, self.num_tags],
#                                     dtype=tf.float32, initializer=self.initializer)
#
#                 b = tf.get_variable("b", shape=[self.num_tags], dtype=tf.float32,
#                                     initializer=tf.zeros_initializer())
#
#                 pred = tf.nn.xw_plus_b(hidden, W, b)
#
#             return tf.reshape(pred, [-1, self.num_steps, self.num_tags])
#
#     # Project layer for idcnn by crownpku
#     # Delete the hidden layer, and change bias initializer
#     def project_layer_idcnn(self, idcnn_outputs, name=None):
#         """
#         :param lstm_outputs: [batch_size, num_steps, emb_size]
#         :return: [batch_size, num_steps, num_tags]
#         """
#         with tf.variable_scope("project" if not name else name):
#             # project to score of tags
#             with tf.variable_scope("logits"):
#                 W = tf.get_variable("W", shape=[self.cnn_output_width, self.num_tags],
#                                     dtype=tf.float32, initializer=self.initializer)
#
#                 b = tf.get_variable("b", initializer=tf.constant(0.001, shape=[self.num_tags]))
#
#                 pred = tf.nn.xw_plus_b(idcnn_outputs, W, b)
#
#             return tf.reshape(pred, [-1, self.num_steps, self.num_tags])
#
#     def loss_layer(self, project_logits, lengths, name=None):
#         """
#         calculate crf loss
#         :param project_logits: [1, num_steps, num_tags]
#         :return: scalar loss
#         """
#         with tf.variable_scope("crf_loss" if not name else name):
#             small = -1000.0
#             # pad logits for crf loss
#             start_logits = tf.concat(
#                 [small * tf.ones(shape=[self.batch_size, 1, self.num_tags]), tf.zeros(shape=[self.batch_size, 1, 1])],
#                 axis=-1)
#             pad_logits = tf.cast(small * tf.ones([self.batch_size, self.num_steps, 1]), tf.float32)
#             logits = tf.concat([project_logits, pad_logits], axis=-1)
#             logits = tf.concat([start_logits, logits], axis=1)
#             targets = tf.concat(
#                 [tf.cast(self.num_tags * tf.ones([self.batch_size, 1]), tf.int32), self.targets], axis=-1)
#
#             self.trans = tf.get_variable(
#                 "transitions",
#                 shape=[self.num_tags + 1, self.num_tags + 1],
#                 initializer=self.initializer)
#             # crf_log_likelihood��һ�������������������ǩ���е�log-likelihood
#             # inputs: һ����״Ϊ[batch_size, max_seq_len, num_tags] ��tensor,
#             # һ��ʹ��BILSTM����֮�����ת��Ϊ��Ҫ�����״��ΪCRF�������.
#             # tag_indices: һ����״Ϊ[batch_size, max_seq_len] �ľ���,��ʵ������ʵ��ǩ.
#             # sequence_lengths: һ����״Ϊ [batch_size] ������,��ʾÿ�����еĳ���.
#             # transition_params: ��״Ϊ[num_tags, num_tags] ��ת�ƾ���
#             # log_likelihood: ����,log-likelihood
#             # transition_params: ��״Ϊ[num_tags, num_tags] ��ת�ƾ���
#             log_likelihood, self.trans = crf_log_likelihood(
#                 inputs=logits,
#                 tag_indices=targets,
#                 transition_params=self.trans,
#                 sequence_lengths=lengths + 1)
#             return tf.reduce_mean(-log_likelihood)
#
#     def create_feed_dict(self, is_train, batch):
#         """
#         :param is_train: Flag, True for train batch
#         :param batch: list train/evaluate data
#         :return: structured data to feed
#         """
#         # ������ֱ��ȥ��batch���ĸ�������ֵ��self.char_inputs, self.seg_inputs, self.targets, self.dropout
#         _, chars, segs, tags = batch
#         feed_dict = {
#             self.char_inputs: np.asarray(chars),
#             self.seg_inputs: np.asarray(segs),
#             self.dropout: 1.0,
#         }
#         if is_train:
#             feed_dict[self.targets] = np.asarray(tags)
#             feed_dict[self.dropout] = self.config["dropout_keep"]
#         return feed_dict
#
#     def run_step(self, sess, is_train, batch):
#         """
#         :param sess: session to run the batchloss
#         :param is_train: a flag indicate if it is a train batch
#         :param batch: a dict containing batch data
#         :return: batch result, loss of the batch or logits
#         """
#         feed_dict = self.create_feed_dict(is_train, batch)
#         if is_train:
#             # �˴�֮����������˶�Ĳ�������sess.run������ΪҪ�õ����еĲ�������ֵ����������Ҫfeed dic��ֻ��һ��feed_dict��������Ǿ���create_feed_dict�޸ĵ���������
#             # ���ʽ�ǣ�chars, segs, tags ��model�ж�Ӧ�������� self.char_inputs   self.seg_inputs  self.targets  self.dropout
#             global_step, loss, _, char_lookup_out, seg_lookup_out, char_inputs_test, seg_inputs_test, embed_test, embedding_test, \
#             model_inputs_test, layerInput_test, conv_test, w_test_1, w_test_2, char_inputs_test = sess.run(
#                 [self.global_step, self.loss, self.train_op, self.char_lookup, self.seg_lookup, self.char_inputs_test,
#                  self.seg_inputs_test, \
#                  self.embed_test, self.embedding_test, self.model_inputs_test, self.layerInput_test, self.conv_test,
#                  self.w_test_1, self.w_test_2, self.char_inputs],
#                 feed_dict)
#             # ��������Ҫ�����������ʼ��model֮�����е���������򶼻�˳��mode��init��ȫ��ִ�С����������ڷ���ѵ����loss����ֵ
#             return global_step, loss
#         else:
#             lengths, logits = sess.run([self.lengths, self.logits], feed_dict)
#             return lengths, logits
#
#     def decode(self, logits, lengths, matrix):
#         """
#         :param logits: [batch_size, num_steps, num_tags]float32, logits
#         :param lengths: [batch_size]int32, real length of each sequence
#         :param matrix: transaction matrix for inference
#         :return:
#         """
#         # inference final labels usa viterbi Algorithm
#         paths = []
#         small = -1000.0
#         start = np.asarray([[small] * self.num_tags + [0]])
#         for score, length in zip(logits, lengths):
#             score = score[:length]
#             pad = small * np.ones([length, 1])
#             logits = np.concatenate([score, pad], axis=1)
#             logits = np.concatenate([start, logits], axis=0)
#             path, _ = viterbi_decode(logits, matrix)
#
#             paths.append(path[1:])
#         return paths
#
#     def evaluate(self, sess, data_manager, id_to_tag):
#         """
#         :param sess: session  to run the model
#         :param data: list of data
#         :param id_to_tag: index to tag name
#         :return: evaluate result
#         """
#         results = []
#         trans = self.trans.eval()
#         for batch in data_manager.iter_batch():
#             strings = batch[0]
#             tags = batch[-1]
#             lengths, scores = self.run_step(sess, False, batch)
#             batch_paths = self.decode(scores, lengths, trans)
#             for i in range(len(strings)):
#                 result = []
#                 string = strings[i][:lengths[i]]
#                 gold = iobes_iob([id_to_tag[int(x)] for x in tags[i][:lengths[i]]])
#                 pred = iobes_iob([id_to_tag[int(x)] for x in batch_paths[i][:lengths[i]]])
#                 # gold = iob_iobes([id_to_tag[int(x)] for x in tags[i][:lengths[i]]])
#                 # pred = iob_iobes([id_to_tag[int(x)] for x in batch_paths[i][:lengths[i]]])
#                 for char, gold, pred in zip(string, gold, pred):
#                     result.append(" ".join([char, gold, pred]))
#                 results.append(result)
#         return results
#