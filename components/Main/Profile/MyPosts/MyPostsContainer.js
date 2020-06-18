import MyPosts from "./MyPosts";
import {addNewPostTextAC, addPostAC} from "../../../Redux/profileReducer";
import {connect} from "react-redux";


const mapStateToProps = (state) => {
	return ({
		postData: state.profilePage.postData,
	})
};
const mapDispatchToProps = (dispatch) => {
	//callbacks for textarea and button in myPosts
	return (
		{
			addNewPostTextCB: postText => {dispatch(addNewPostTextAC(postText))},
			addPostCB: () => {dispatch(addPostAC())},
		}
	)
};

export default connect(mapStateToProps, mapDispatchToProps)(MyPosts)