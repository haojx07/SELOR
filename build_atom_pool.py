"""
The script to build atom pools
"""
import os
import pickle
import time
from tqdm import tqdm
import numpy as np

# Import from custom files
from selor_utils import atom as at
from selor_utils import dataset as ds
from selor_utils import utils

if __name__ == "__main__":
    args = utils.parse_arguments()

    dtype = ds.get_dataset_type(args.dataset)
    btype = ds.get_base_type(args.base)

    assert dtype==btype

    seed = args.seed
    utils.reset_seed(seed)

    train_df, valid_df, test_df = ds.load_data(dataset=args.dataset)

    if args.save_dir not in os.listdir('.'):
        os.system(f'mkdir ./{args.save_dir}')

    col_label = ds.get_label_column(args.dataset)
    train_y = np.array(train_df[col_label]).astype(int)
    test_y = np.array(test_df[col_label]).astype(int)

    pos_type = ds.get_context_columns(args.dataset)
    build_start = time.time()
    if dtype == 'nlp':
        print('Create atom tokenizer.')
        atom_tokenizer = at.AtomTokenizer(
            train_df,
            dataset=args.dataset
        )

        if 'atom_tokenizer' not in os.listdir(f'./{args.save_dir}'):
            os.system(f'mkdir ./{args.save_dir}/atom_tokenizer')

        with open(f'./{args.save_dir}/atom_tokenizer/atom_tokenizer_{args.dataset}.pkl', 'wb') as f:
            pickle.dump(atom_tokenizer, f, pickle.HIGHEST_PROTOCOL)

        print('Calculating word counts of train df')
        train_x = at.get_word_count(
            train_df,
            tokenizer=atom_tokenizer,
            pos_type=pos_type
        )

        print('Calculating word counts of test df')
        test_x = at.get_word_count(
            test_df,
            tokenizer=atom_tokenizer,
            pos_type=pos_type
        )

    elif dtype == 'tab':
        atom_tokenizer = None
        train_x = np.array(train_df.drop(columns=[col_label]))
        test_x = np.array(test_df.drop(columns=[col_label]))
    else:
        raise NotImplementedError("We only support NLP and tabular dataset now.")

    if 'atom_pool' not in os.listdir(f'./{args.save_dir}'):
        os.system(f'mkdir ./{args.save_dir}/atom_pool')

    # Build atom pool.
    if dtype == 'nlp':
        ap = at.AtomPool(
            train_x,
            train_y,
            dtype=dtype,
            tokenizer=atom_tokenizer,
        )

        # Sort by frequency
        s = np.sum(train_x, axis=0)
        a = np.argsort(s)[::-1]

        # Add dummy atom
        ap.add_atom(
            c_type='dummy',
            context=None,
            bigger=None,
            target=None,
            position=None,
            pos_type=None,
        )

        # Exclude meaningless tokens
        remove_list = [
            '[PAD]', '.', ',', '', '[UNK]',
            'the', 'a', 'an',
            'i', 'my', 'me',
            'he', 'him', 'his',
            'she', 'her',
            'it', 'its',
            'we', 'our', 'us',
            'you', 'your',
            'they', 'their', 'them',
            'this', 'that', 'there', 'here',
            'to', 'of', 'in', 'for', 'and', 'with', 'on', 'at', 'as', 'from',
            'will', 'would',
            'is', 'was', 'are', 'were', 'be', 'been',
            'have', 'had', 'told', 'said', 'asked', 'asking',
            'given', 'telling',
        ]

        # Add atoms according to their frequency
        cur_num_atoms = 0
        for i, feature_idx in enumerate(tqdm(a) ):
            feature_idx = int(feature_idx)
            word = feature_idx % atom_tokenizer.vocab_size
            pos = feature_idx // atom_tokenizer.vocab_size

            w = atom_tokenizer.idx2word[word]
            if w not in remove_list and len(w) > 1 and w.isalpha():
                ap.add_atom(
                    c_type='text',
                    context=word,
                    bigger=True,
                    target=0.5,
                    position=pos,
                    pos_type=pos_type,
                )

                cur_num_atoms += 1
                if cur_num_atoms == args.num_atoms:
                    break

        ap.display_atoms(cur_num_atoms)
        n_atom = ap.num_atoms()
        print(f'{n_atom} atoms added')

        # For efficient memory use
        ap.train_x = None
        ap.train_y = None

        atom_pool_path = f'./{args.save_dir}/atom_pool/'
        atom_pool_path += f'atom_pool_{args.dataset}_num_atoms_{args.num_atoms}.pkl'
        with open(atom_pool_path, 'wb') as f:
            pickle.dump(ap, f, pickle.HIGHEST_PROTOCOL)

    elif dtype == 'tab':
        tabular_column_type = ds.get_tabular_column_type(dataset=args.dataset)
        tabular_info = ds.load_tabular_info(dataset=args.dataset)
        cat_map, numerical_threshold, numerical_max = tabular_info
        categorical_x_col, numerical_x_col, y_col = tabular_column_type

        ap = at.AtomPool(
            train_x,
            train_y,
            dtype=dtype,
            tabular_info=tabular_info,
            tabular_column_type=tabular_column_type,
        )

        ap.add_atom(
            c_type='dummy',
            context=None,
            bigger=None,
            target=None,
            position=None
        )
        for cat in numerical_x_col:
            m = numerical_max[cat]
            for n in numerical_threshold[cat]:
                ap.add_atom('numerical', cat, True, n / m)
                ap.add_atom('numerical', cat, False, n / m)

        for cat in categorical_x_col:
            for k in cat_map[f'{cat}_idx2key']:
                ap.add_atom('categorical', cat, True, k)
                ap.add_atom('categorical', cat, False, k)

        ap.display_atoms()
        n_atom = ap.num_atoms()
        print(f'{n_atom} atoms added')

        # For efficient memory use
        ap.train_x = None
        ap.train_y = None

        with open(f'./{args.save_dir}/atom_pool/atom_pool_{args.dataset}.pkl', 'wb') as f:
            pickle.dump(ap, f, pickle.HIGHEST_PROTOCOL)
    else:
        raise NotImplementedError("We only support NLP and tabular dataset now.")

    build_end = time.time()
    print(f'Building time: {build_end - build_start} s')
