//actions
const ADD_NEW_POST_TEXT = 'ADD_NEW_POST_TEXT';
const ADD_POST = 'ADD_POST';

//начальные значения для инициализации state redux
let initialState = {
	newMsgTxt: '',
	postData: [
		{
			id: 1,
			msg: 'Message 1 Lorem ipsum dolor sit amet. Lorem ipsum dolor sit amet.Lorem ipsum dolor sit amet.' +
				' Lorem ipsum dolor sit amet.',
			like: 5,
			dislike: 3,
			key: 1,
		},
		{
			id: 2,
			msg: 'Message 2 Lorem ipsum dolor sit amet.Lorem ipsum dolor sit amet. Lorem ipsum dolor sit amet.Lorem ipsum dolor sit amet.',
			like: 4,
			dislike: 1,
			key: 2,
		},
	],
};

let profileReducer = (state = initialState, action) => {
	switch (action.type) {
		// add new post in profilePage-postData
		case 'ADD_POST':
			return {
				...state, postData: [...state.postData, {
					id: 3,
					msg: state.newMsgTxt,
					like: 777,
					dislike: 666,
					key: 3,
				}], newMsgTxt: "",
			};
		
		// add text in textarea in profilePage
		case 'ADD_NEW_POST_TEXT':
			return {...state, newMsgTxt: action.messageTxt};
		
		default:
			return state;
	}
};

// action creators
//for MyPosts NewPostText addPost
export const addNewPostText = messageTxt => ({type: ADD_NEW_POST_TEXT, messageTxt: messageTxt});
export const addPost = () => ({type: ADD_POST});

export default profileReducer;