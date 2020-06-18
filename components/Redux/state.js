import dialogsReducer from "./dialogsReducer";
import profileReducer from "./profileReducer";

let store = {
	
	_state: {
		profilePage: {
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
		},
		dialogsPage: {
			dialogData: [
				{id: 1, name: 'User'},
				{id: 2, name: 'User'},
				{id: 3, name: 'User'},
				{id: 4, name: 'User'},
			],
			messageData: [
				{id: 1, message: 'text Lorem ipsum dolor. Lorem ipsum dolor. Lorem ipsum dolor.'},
				{id: 2, message: 'text Lorem ipsum dolor. Lorem ipsum dolor. Lorem ipsum dolor.'},
				{id: 3, message: 'text Lorem ipsum dolor. Lorem ipsum dolor. Lorem ipsum dolor.'},
				{id: 4, message: 'text Lorem ipsum dolor. Lorem ipsum dolor. Lorem ipsum dolor.'},
			],
			newCommentTxt: '',
		},
	},
	
	//state getter
	getState() {
		return this._state;
	},
	
	// empty variable function for subscriber
	_rerenderEntireTree() {
	},
	
	// subscribe for rerenderEntireTree form index.js
	subscribe(observer) {
		this._rerenderEntireTree = observer;
	},
	
	// dispatcher actions, take only need part of state for each reducer. And rewrite this part of state.
	dispatch(action) {
		this._state.dialogsPage = dialogsReducer(this._state.dialogsPage, action);
		this._state.profilePage = profileReducer(this._state.profilePage, action);
		this._rerenderEntireTree();
	},
};

export default store;
window.store = store;