// import userLogo from "../../../src/Images/logo.svg";
//actions
// const ADD_NEW_COMMENT_TEXT = 'ADD_NEW_COMMENT_TEXT';
const GET_USERS = 'GET_USERS';
const FOLLOW = 'FOLLOW';
const UNFOLLOW = 'UNFOLLOW';
const TOTAL_PAGES = 'TOTAL_PAGES';
const CHOOSED_PAGE = 'CHOOSED_PAGE';


//начальные значения для инициализации state redux
let initialState = {
	usersData: [],
	totalUsers: 50,
	usersOnPage: 50,
	currentPage: 1,
	choosedPage: 1,
	totalPages: 1
};

export default (state = initialState, action) => {
	//поверхностное копирование state, принцип иммутабельности
	switch (action.type) {
		// current page in pagination
		case 'CHOOSED_PAGE':
			return {...state, currentPage: state.choosedPage, choosedPage: action.choosedPage};
		// number of pages in pagination
		case 'TOTAL_PAGES':
			return {state};
		// adding text in textarea in dialogsPage
		case 'GET_USERS':
			//возвращает копию state, и обновляет newCommentTxt
			return {...state, usersData: action.usersData.items, currentPage: state.choosedPage, totalPages: Math.ceil(action.usersData.totalCount / state.usersOnPage)};
		
		// add new comment in dialogsPage-dialogData
		case 'FOLLOW':
			return {
				...state,
				usersData: state.usersData.map(u => {
					if (u.id === action.userId) {
						return {...u, follow: true}
					}
					return { ...u}
				})
			};
		
		case 'UNFOLLOW':
			return {
				...state,
				usersData: state.usersData.map(u => {
					if (u.id === action.userId) {
						return {...u, follow: false}
					}
					return { ...u}
				})
			};
		// case 'ADD_NEW_COMMENT':
		// 	//возвращает копию state, добавляет текст нового сообщения и обновляет newCommentTxt
		// 	return {...state, messageData: [...state.messageData, {id: 5, message: state.newCommentTxt}],	newCommentTxt: ""};
		
		default:
			return state;
	}
}

// action creators
//for Dialogs NewCommentText andNewComment
// export const addNewCommentText = messageTxt => ({type: ADD_NEW_COMMENT_TEXT, messageTxt: messageTxt});
export const choosedPageAC = (choosedPage) => ({type: CHOOSED_PAGE, choosedPage});
export const totalPagesAC = () => ({type: TOTAL_PAGES, });
export const getUsersAC = (usersData) => ({type: GET_USERS, usersData: usersData});
export const followAC = (userId) => ({type: FOLLOW, userId: userId});
export const unfollowAC = (userId) => ({type: UNFOLLOW, userId: userId});
